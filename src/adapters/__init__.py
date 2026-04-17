"""
Domain adapters: pluggable implementations for each domain (climbing, hiking, skiing).

An adapter encapsulates:
- How to score an objective in that domain
- How to format context for the LLM
- Which integrations to use
- Domain-specific prompt templates
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import Dict, List, Any, Optional, Tuple
from ..domain.objective_models import Objective, ObjectiveRecommendation
from ..domain.recommendation_models import DayPlan
from ..integrations.alerts import AlertProvider
from ..integrations.content import ContentProvider
from ..models import WeatherDay, Scores
from ..scoring.generic import c_to_f, mps_to_mph


def _format_trip_window(start_date: str, end_date: str) -> str:
    """Return a concise day label for a trip window."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return "Trip window"

    if start == end:
        return start.strftime("%A")
    return f"{start.strftime('%a')} to {end.strftime('%a')}"


def _includes_weekend(start_date: str, end_date: str) -> bool:
    """True when any date in the requested window falls on a weekend."""
    try:
        current = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except ValueError:
        return False

    while current <= end:
        if current.weekday() >= 5:
            return True
        current = date.fromordinal(current.toordinal() + 1)
    return False


def _yds_to_numeric(grade: Optional[str]) -> Optional[float]:
    """
    Convert simple Yosemite Decimal grades like 5.10a to a sortable float.
    """
    if not grade:
        return None

    grade = grade.strip().lower()
    if not grade.startswith("5."):
        return None

    letter_bonus = {"a": 0.0, "b": 0.1, "c": 0.2, "d": 0.3}
    numeric = grade[2:]
    number_chars = []
    letter = ""

    for char in numeric:
        if char.isdigit():
            number_chars.append(char)
        elif char in letter_bonus:
            letter = char
            break

    if not number_chars:
        return None

    return float("".join(number_chars)) + letter_bonus.get(letter, 0.0)


def _parse_grade_range(grade_range: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    """Parse a simple range like 5.6-5.12c."""
    if not grade_range or "-" not in grade_range:
        return None, None
    min_grade, max_grade = [part.strip() for part in grade_range.split("-", 1)]
    return _yds_to_numeric(min_grade), _yds_to_numeric(max_grade)


class ObjectiveAdapter(ABC):
    """
    Abstract base class for domain-specific adapters.
    
    Each domain (climbing, hiking, skiing) provides an implementation
    to customize behavior without forking the core orchestration.
    """

    @abstractmethod
    def get_location_catalog(self) -> Dict[str, Dict[str, Any]]:
        """
        Return the domain-owned location/objective seed catalog.

        This catalog is intentionally domain-specific: climbing, hiking,
        and future skiing can store different metadata and use different
        source systems without being forced into one ingestion schema.
        """
        pass

    def get_alert_provider(self, objective: Objective) -> Optional[AlertProvider]:
        """
        Return an alert provider for this domain/objective, if one exists.

        Domains without a meaningful alert source can return None.
        """
        return None

    def get_content_providers(self, objective: Objective) -> List[ContentProvider]:
        """
        Return content providers for enrichment/RAG for this domain/objective.

        This remains optional so each domain can grow its data pipeline
        independently.
        """
        return []
    
    @abstractmethod
    def compute_scores(
        self,
        objective: Objective,
        weather_days: List[WeatherDay],
        context: Dict[str, Any],
    ) -> Scores:
        """
        Compute domain-specific scores for the objective.
        
        Args:
            objective: The objective being evaluated
            weather_days: Weather forecast for the location
            context: Additional context (alerts, RAG chunks, etc.)
        
        Returns:
            Scores object with domain-specific breakdown
        """
        pass
    
    @abstractmethod
    def format_context_for_llm(
        self,
        objective: Objective,
        scores: Scores,
        context: Dict[str, Any],
    ) -> str:
        """
        Format context into a string suitable for LLM prompting.
        
        Args:
            objective: The objective
            scores: Computed scores
            context: Additional context
        
        Returns:
            Formatted context string for the LLM prompt
        """
        pass
    
    @abstractmethod
    def get_system_message(self) -> str:
        """Return the domain-specific LLM system message."""
        pass
    
    @abstractmethod
    def parse_verdict(self, llm_output: str, scores: Scores) -> str:
        """
        Parse the LLM output to extract a verdict.
        
        Returns one of: "GO", "CAUTION", "NO-GO"
        """
        pass
    
    @abstractmethod
    def generate_plan(
        self,
        objective: Objective,
        scores: Optional[Scores],
        weather_days: List[WeatherDay],
        is_primary: bool = True,
    ) -> DayPlan:
        """
        Generate a domain-specific day plan for the objective.
        
        Args:
            objective: The objective to plan for
            scores: Computed scores (may be None)
            weather_days: Weather forecast
            is_primary: Whether this is the primary or backup plan
        
        Returns:
            DayPlan with domain-specific details (routes, gear, timing, etc.)
        """
        pass


class HikingAdapter(ObjectiveAdapter):
    """Adapter for hiking domain. Thin wrapper around existing logic."""

    def get_location_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Return the hiking location catalog."""
        from ..config import PARKS

        return PARKS

    def get_alert_provider(self, objective: Objective) -> Optional[AlertProvider]:
        """Hiking currently uses NPS alerts."""
        from ..integrations.alerts.nps import NPSAlertProvider

        return NPSAlertProvider()

    def get_content_providers(self, objective: Objective) -> List[ContentProvider]:
        """Hiking currently uses NPS content."""
        from ..integrations.content import NPSContentProvider

        return [NPSContentProvider()]
    
    def compute_scores(
        self,
        objective: Objective,
        weather_days: List[WeatherDay],
        context: Dict[str, Any],
    ) -> Scores:
        """Use existing hiking scoring logic."""
        from ..models import TripRequest

        # Adapt Objective back to TripRequest for backward compat
        trip = TripRequest(
            park_code=objective.location_id,
            start_date=objective.start_date,
            end_date=objective.end_date,
            activity_type="hiking",
            hiker_profile=objective.constraints.skill_level,
            constraints={
                "max_hike_hours": objective.constraints.max_duration_hours,
            } if objective.constraints.max_duration_hours else None,
        )

        # Extract alerts from context
        alerts = context.get("alerts", [])
        if not isinstance(alerts, list):
            alerts = []

        # Import compute_scores from the top-level scoring.py file
        # We use a dynamic import to avoid collision with src.scoring/ package
        import sys
        import os
        import importlib.util
        
        # Get the path to scoring.py (not scoring/__init__.py)
        src_dir = os.path.dirname(os.path.dirname(__file__))
        scoring_py = os.path.join(src_dir, 'scoring.py')
        
        # Load scoring.py as a module
        spec = importlib.util.spec_from_file_location("scoring_py_module", scoring_py)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {scoring_py}")
        
        scoring_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scoring_module)
        
        return scoring_module.compute_scores(trip, weather_days, alerts)
    
    def format_context_for_llm(
        self,
        objective: Objective,
        scores: Scores,
        context: Dict[str, Any],
    ) -> str:
        """Use existing hiking context formatting."""
        from ..prompt_builder import _format_weather_section
        
        weather_days = context.get("weather", [])
        return _format_weather_section(weather_days)
    
    def get_system_message(self) -> str:
        """Hiking-specific system message."""
        return (
            "You are a cautious, realistic, safety-focused hiking advisor "
            "for U.S. National Parks. You give practical, conservative advice "
            "and never overstate safety."
        )
    
    def parse_verdict(self, llm_output: str, scores: Scores) -> str:
        """Simple heuristic: use score to determine verdict."""
        if scores.trip_readiness_score >= 75:
            return "GO"
        elif scores.trip_readiness_score >= 55:
            return "CAUTION"
        else:
            return "NO-GO"
    
    def generate_plan(
        self,
        objective: Objective,
        scores: Optional[Scores],
        weather_days: List[WeatherDay],
        is_primary: bool = True,
    ) -> DayPlan:
        """Generate a hiking day plan."""
        from datetime import datetime
        from ..config import get_objective_location
        
        location_meta = get_objective_location("hiking", objective.location_id)
        
        day_label = _format_trip_window(objective.start_date, objective.end_date)
        start_time = "08:00 AM"
        estimated_duration = objective.constraints.max_duration_hours or 6.0
        approach_minutes = objective.constraints.max_approach_minutes or 30
        
        plan = DayPlan(
            day=day_label,
            location_name=location_meta.get("name", objective.location_id),
            start_time=start_time,
            routes_or_trails=[
                "Suggested hike in {}".format(location_meta.get("name")),
                "Difficulty: {}".format(objective.constraints.skill_level or "moderate"),
            ],
            expected_duration_hours=estimated_duration,
            approach_minutes=approach_minutes,
            gear_required="Hiking boots, backpack, water, sun protection",
            weather_specific_notes="Check NPS alerts before departure",
        )
        
        return plan


class ClimbingAdapter(ObjectiveAdapter):
    """Adapter for climbing domain. Stub for v1."""

    def get_location_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Return the climbing location catalog."""
        from ..config import CLIMBING_AREAS

        return CLIMBING_AREAS
    
    def compute_scores(
        self,
        objective: Objective,
        weather_days: List[WeatherDay],
        context: Dict[str, Any],
    ) -> Scores:
        """Compute a practical v1 sendability score for climbing objectives."""
        from ..models import Scores

        metadata = context.get("location_metadata", {})
        notes: List[str] = []
        risk_flags: List[str] = []

        if not weather_days:
            notes.append("No forecast data available, so sendability is conservative.")
            return Scores(
                park_code=objective.location_id,
                start_date=objective.start_date,
                end_date=objective.end_date,
                access_score=75.0,
                weather_score=55.0,
                risk_score=45.0,
                crowd_score=65.0,
                trip_readiness_score=63.0,
                risk_flags=["forecast_uncertain"],
                notes=notes,
            )

        weather_score = 85.0
        wet_days = 0
        strong_wind_days = 0
        temp_extreme_days = 0

        for day in weather_days:
            high_f = c_to_f(day.temp_max_c)
            low_f = c_to_f(day.temp_min_c)
            precip_pct = day.precip_probability * 100.0
            wind_mph = mps_to_mph(day.wind_speed_max_mps)

            if precip_pct >= 40:
                wet_days += 1
                weather_score -= 18.0
                notes.append(
                    f"{day.date}: rain probability near {precip_pct:.0f}% means likely damp rock."
                )
            elif precip_pct >= 20:
                weather_score -= 8.0
                notes.append(
                    f"{day.date}: scattered precipitation may delay the start of the day."
                )

            if wind_mph >= 20:
                strong_wind_days += 1
                weather_score -= 12.0
                notes.append(
                    f"{day.date}: winds near {wind_mph:.0f} mph could make exposed climbing unpleasant."
                )
            elif wind_mph >= 12:
                weather_score -= 4.0
                notes.append(f"{day.date}: breezy conditions favor more sheltered objectives.")

            if high_f >= 90 or low_f <= 32:
                temp_extreme_days += 1
                weather_score -= 10.0
                notes.append(
                    f"{day.date}: temperatures swing into an efficiency-limiting range for climbing."
                )

        if wet_days:
            risk_flags.append("wet_rock")
        if strong_wind_days:
            risk_flags.append("wind_strong")
        if temp_extreme_days:
            risk_flags.append("temperature_extreme")

        wetness_hours = metadata.get("typical_wetness_after_rain_hours")
        if wet_days and wetness_hours:
            notes.append(
                f"This area often needs about {wetness_hours} hours to dry after rain."
            )

        weather_score = max(0.0, min(100.0, weather_score))

        access_score = 90.0
        if metadata.get("permit_required"):
            access_score -= 10.0
            notes.append("Permit logistics reduce the simplicity of this plan.")
        if (
            objective.constraints.max_approach_minutes is not None
            and objective.constraints.max_approach_minutes <= 15
            and metadata.get("approach_difficulty") == "moderate"
        ):
            access_score -= 8.0
            notes.append("Your approach limit is tight for this area's usual approach profile.")

        crowd_baseline = {
            "low": 86.0,
            "medium": 74.0,
            "high": 62.0,
        }.get(str(metadata.get("crowd_tendency", "medium")).lower(), 72.0)
        if _includes_weekend(objective.start_date, objective.end_date):
            crowd_baseline -= 10.0
            if str(metadata.get("crowd_tendency", "")).lower() == "high":
                risk_flags.append("crowd_likely_weekend")
                notes.append("Weekend timing plus a popular area means an early start matters.")
        crowd_score = max(0.0, min(100.0, crowd_baseline))

        grade_min, grade_max = _parse_grade_range(metadata.get("grade_range"))
        requested_grade = _yds_to_numeric(
            objective.constraints.custom_prefs.get("grade_target")
            if objective.constraints.custom_prefs
            else None
        )
        if requested_grade is None:
            requested_grade = _yds_to_numeric(objective.description)
        if requested_grade is None:
            requested_grade = _yds_to_numeric(context.get("requested_grade_max"))

        if requested_grade is not None and grade_max is not None and requested_grade > grade_max:
            access_score -= 8.0
            risk_flags.append("grade_mismatch")
            notes.append("Requested grade sits above this area's core range.")

        total_weight = 0.3 + 0.5 + 0.2
        trip_readiness = (
            0.3 * access_score +
            0.5 * weather_score +
            0.2 * crowd_score
        ) / total_weight
        trip_readiness = max(0.0, min(100.0, trip_readiness))
        risk_score = max(0.0, min(100.0, 100.0 - trip_readiness))

        return Scores(
            park_code=objective.location_id,
            start_date=objective.start_date,
            end_date=objective.end_date,
            access_score=access_score,
            weather_score=weather_score,
            risk_score=risk_score,
            crowd_score=crowd_score,
            trip_readiness_score=trip_readiness,
            risk_flags=sorted(set(risk_flags)),
            notes=notes or ["Forecast and access look generally workable."],
        )
    
    def format_context_for_llm(
        self,
        objective: Objective,
        scores: Scores,
        context: Dict[str, Any],
    ) -> str:
        """Placeholder: return basic context."""
        return f"Climbing objective at {objective.location_id}"
    
    def get_system_message(self) -> str:
        """Climbing-specific system message."""
        return (
            "You are a cautious, experienced climbing advisor. "
            "You prioritize safety and realistic assessment of conditions. "
            "You never overstate the sendability of an objective."
        )
    
    def parse_verdict(self, llm_output: str, scores: Scores) -> str:
        """Placeholder: use score-based heuristic."""
        if scores.trip_readiness_score >= 75:
            return "GO"
        elif scores.trip_readiness_score >= 55:
            return "CAUTION"
        else:
            return "NO-GO"
    
    def generate_plan(
        self,
        objective: Objective,
        scores: Optional[Scores],
        weather_days: List[WeatherDay],
        is_primary: bool = True,
    ) -> DayPlan:
        """Generate a climbing day plan."""
        from ..config import get_objective_location

        try:
            location_meta = get_objective_location("climbing", objective.location_id)
        except KeyError:
            custom_prefs = objective.constraints.custom_prefs or {}
            location_meta = {
                "name": custom_prefs.get("resolved_location_name", objective.location_id),
                "crowd_tendency": "medium",
                "primary_climb_types": custom_prefs.get("resolved_climb_types", ["climbing"]),
                "grade_range": custom_prefs.get("resolved_grade_range", "broad grades"),
            }
        
        day_label = _format_trip_window(objective.start_date, objective.end_date)
        crowd_tendency = str(location_meta.get("crowd_tendency", "medium")).lower()
        if is_primary and crowd_tendency == "high":
            start_time = "07:30 AM"
        elif is_primary:
            start_time = "08:30 AM"
        else:
            start_time = "09:00 AM"
        estimated_duration = objective.constraints.max_duration_hours or 4.0
        approach_minutes = objective.constraints.max_approach_minutes or 15
        climb_types = ", ".join(location_meta.get("primary_climb_types", ["climbing"]))
        grade_range = location_meta.get("grade_range", "broad grades")
        weather_note = "Start with dry stone and reassess if showers build."
        if weather_days:
            first_day = weather_days[0]
            if first_day.precip_probability >= 0.3:
                weather_note = "Treat the timing as flexible; damp rock may push the start later."
            elif first_day.wind_speed_max_mps >= 6.7:
                weather_note = "Favor sheltered walls if wind builds through the afternoon."

        gear = "Harness, helmet, shoes, belay kit"
        if "sport" in location_meta.get("primary_climb_types", []):
            gear += ", quickdraws"
        if "trad" in location_meta.get("primary_climb_types", []):
            gear += ", light trad rack"
        if "boulder" in location_meta.get("primary_climb_types", []):
            gear += ", pads"
        
        plan = DayPlan(
            day=day_label,
            location_name=location_meta.get("name", objective.location_id),
            start_time=start_time,
            routes_or_trails=[
                f"Primary style: {climb_types}",
                f"Area grade range: {grade_range}",
                f"Plan length: about {estimated_duration:.1f} hours car-to-car",
            ],
            expected_duration_hours=estimated_duration,
            approach_minutes=approach_minutes,
            gear_required=gear,
            weather_specific_notes=weather_note,
        )
        
        return plan


# Factory for getting the right adapter
def get_adapter(domain: str) -> ObjectiveAdapter:
    """Get the adapter for a specific domain."""
    if domain == "hiking":
        return HikingAdapter()
    elif domain == "climbing":
        return ClimbingAdapter()
    else:
        raise ValueError(f"Unknown domain: {domain}")
