"""
Domain-agnostic objective models.

An "Objective" is something a user wants to evaluate:
- A climbing crag + route grade
- A hiking trail in a park
- A ski descent in the backcountry

All objectives have location, timing, and user constraints.
Domain-specific fields (e.g., route grade, avalanche level) live in subclasses.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import date


@dataclass
class UserConstraints:
    """
    Domain-agnostic user constraints/preferences for an objective.
    
    Specific domains can extend or interpret these fields differently:
    - Hiking: max_hours = hike duration
    - Climbing: max_hours = approach + climbing time
    - Skiing: max_hours = total tour duration
    """
    max_duration_hours: Optional[float] = None
    max_approach_minutes: Optional[int] = None
    commitment_level: str = "flexible"  # "walk-up", "half-day", "full-day", "multi-day"
    activity_restrictions: List[str] = field(default_factory=list)  # e.g., ["no_exposure", "bolted_only"]
    partner_count: Optional[int] = None
    skill_level: str = "intermediate"  # domain-specific interpretation
    custom_prefs: Dict[str, Any] = field(default_factory=dict)  # extensible for future needs


@dataclass
class Objective:
    """
    Base objective: the thing being evaluated.
    
    Subclasses (HikingObjective, ClimbingObjective, SkiObjective) add domain-specific fields.
    """
    objective_id: str                        # Unique ID; can be UUID or generated
    location_id: str                         # e.g., "rrg", "yose", "bishop", "tahoeBackcountry"
    location_type: str                       # e.g., "climbing_area", "national_park", "ski_zone"
    domain: str                              # e.g., "climbing", "hiking", "skiing"
    
    start_date: str                          # ISO format
    end_date: str                            # ISO format
    
    constraints: UserConstraints = field(default_factory=UserConstraints)
    
    # Optional metadata
    user_id: Optional[str] = None            # For multi-user support later
    description: Optional[str] = None        # User notes
    
    @property
    def duration_days(self) -> int:
        """Convenience: calculate trip duration."""
        from datetime import datetime
        start = datetime.fromisoformat(self.start_date).date()
        end = datetime.fromisoformat(self.end_date).date()
        return (end - start).days + 1


@dataclass
class ObjectiveLocation:
    """
    Metadata about a location (crag, park, ski zone, etc.).
    Used to configure weather, alerts, and domain-specific behavior.
    """
    location_id: str
    name: str
    lat: float
    lon: float
    location_type: str                       # "climbing_area", "national_park", etc.
    primary_domain: str                      # "climbing", "hiking", "skiing"
    timezone: str
    
    # Optional: domain-specific metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectiveRecommendation:
    """
    A recommendation produced by the advisor.
    Includes the verdict, scores, explanation, and next steps.
    """
    objective: Objective
    verdict: str                             # "GO", "CAUTION", "NO-GO"
    overall_score: float                     # 0–100
    
    # Scores by dimension (domain-specific, but commonly present)
    component_scores: Dict[str, float]       # {"weather": 75, "grade_fit": 85, ...}
    
    # Risk and reasoning
    risk_flags: List[str]                    # e.g., ["wind_strong", "wet_rock"]
    short_explanation: str                   # 1–2 sentences
    detailed_explanation: Optional[str]      # LLM-generated paragraph
    
    # Domain-specific recommendations (populated by domain adapter)
    recommendations: Dict[str, Any] = field(default_factory=dict)  # e.g., {"primary_routes": [...]}
    
    # Context used in evaluation
    conditions_at_location: Optional[Dict[str, Any]] = None  # weather, alerts, etc.


# Backward compatibility: alias for old naming
ObjectiveRequest = Objective
