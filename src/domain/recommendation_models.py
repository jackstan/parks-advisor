"""
Domain-specific recommendation models and request/response types.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date
from .objective_models import Objective, UserConstraints


@dataclass
class RecommendationRequest:
    """
    User request for planning advice.
    Combines objective preferences + planning horizon + constraints.
    """
    domain: str                        # "climbing", "hiking", "skiing"
    location_ids: Optional[List[str]] = None  # Preferred locations; if None, auto-suggest
    
    # Timing
    start_date: str = ""               # ISO format
    end_date: str = ""                 # ISO format
    
    # Domain-specific constraints
    grade_min: Optional[str] = None    # e.g., "5.9" for climbing, "easy" for hiking
    grade_max: Optional[str] = None    # e.g., "5.11a"
    
    # Generic constraints
    max_duration_hours: Optional[float] = None
    max_approach_minutes: Optional[int] = None
    commitment_level: str = "flexible"
    skill_level: str = "intermediate"
    
    # Context
    partner_count: Optional[int] = None
    custom_notes: Optional[str] = None


@dataclass
class ObjectiveCandidate:
    """
    A candidate objective during evaluation.
    Progresses from initial suggestion → scored → ranked → selected.
    """
    # Identity
    candidate_id: str
    objective: Objective
    
    # Metadata (populated during evaluation)
    location_name: str = ""
    location_metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Scores (populated during evaluation)
    weather_days: List[Any] = field(default_factory=list)  # WeatherDay
    scores: Optional[Any] = None  # Scores dataclass
    overall_sendability_score: float = 0.0
    route_options: List[Any] = field(default_factory=list)
    
    # Ranking
    rank: int = 0  # Will be set after sorting
    match_reason: str = ""  # Why this candidate was suggested
    selection_reason: str = ""  # Why this candidate was ultimately recommended
    location_coordinates: Optional[Dict[str, float]] = None
    area_bounds: Optional[Dict[str, float]] = None


@dataclass
class MapPoint:
    """
    A UI-ready map marker for objective and plan rendering.
    """
    point_id: str
    label: str
    lat: float
    lon: float
    point_type: str = "objective"
    role: str = "candidate"
    score: Optional[float] = None
    description: str = ""


@dataclass
class RouteOption:
    """
    A normalized route-level option for climbing retrieval and UI display.
    """
    route_id: str
    name: str
    area_name: str
    parent_area_name: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    grade: Optional[str] = None
    length_ft: Optional[int] = None
    route_types: List[str] = field(default_factory=list)
    safety: Optional[str] = None
    left_right_index: Optional[int] = None
    source_name: str = "openbeta"
    source_route_id: Optional[str] = None


@dataclass
class DayPlan:
    """
    A simple itinerary for a single climbing/hiking day.
    """
    day: str                           # "Saturday", "Sunday"
    location_name: str
    start_time: str                    # "8:00 AM"
    routes_or_trails: List[str]        # ["Motherlode (5.10a)", "Screwdriver (5.10a)"]
    expected_duration_hours: float
    approach_minutes: int
    gear_required: str                 # e.g., "Sport rack, 10x quickdraws"
    weather_specific_notes: str        # "Approach wet until 8:30 AM"
    location_coordinates: Optional[Dict[str, float]] = None
    area_bounds: Optional[Dict[str, float]] = None
    route_coordinates: List[Dict[str, float]] = field(default_factory=list)


@dataclass
class PlannerRecommendation:
    """
    Final recommendation from the planner.
    Includes verdict, objectives, plans, and explanation.
    
    This is the output sent to UI, LLM, or user.
    """
    # Verdict
    sendability_verdict: str           # "GO", "CAUTION", "NO-GO"
    overall_sendability_score: float   # 0–100
    
    # Objectives
    primary_objective: ObjectiveCandidate
    backup_objective: ObjectiveCandidate
    
    # Conditions
    conditions_summary: Dict[str, Any]  # {"temperature_f": 72, "wind_mph": 12, ...}
    sendability_scores: Dict[str, float]  # {"grade_alignment": 85, ...}
    
    # Risk and reasoning
    risk_flags: List[str]              # ["wind_moderate", "crowd_likely"]
    short_explanation: str             # 1–2 sentences
    detailed_explanation: Optional[str] = None  # LLM-generated
    
    # Plans
    primary_plan: DayPlan = field(default_factory=lambda: DayPlan(
        day="", location_name="", start_time="", routes_or_trails=[],
        expected_duration_hours=0, approach_minutes=0, gear_required="",
        weather_specific_notes=""
    ))
    backup_plan: DayPlan = field(default_factory=lambda: DayPlan(
        day="", location_name="", start_time="", routes_or_trails=[],
        expected_duration_hours=0, approach_minutes=0, gear_required="",
        weather_specific_notes=""
    ))

    # Map rendering
    map_points: List[MapPoint] = field(default_factory=list)
    
    # Debug/transparency
    debug_context: Dict[str, Any] = field(default_factory=dict)
