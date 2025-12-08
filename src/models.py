from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class Park:
    park_code: str
    name: str
    states: List[str]
    type: str
    lat: float
    lon: float
    timezone: str
    elevation_band: Optional[str] = None
    primary_activities: Optional[List[str]] = None
    nps_url: Optional[str] = None
    season_notes: Optional[str] = None


@dataclass
class TripRequest:
    park_code: str
    start_date: str
    end_date: str
    activity_type: str          # e.g., "hiking", "camping"
    hiker_profile: str          # e.g., "beginner", "intermediate", "advanced"  
    trails_of_interest: Optional[List[str]] = None
    constraints: Optional[Dict] = None

@dataclass
class WeatherDay:
    park_code: str
    date: str
    temp_min_c: float
    temp_max_c: float
    precip_mm: float
    precip_probability: float
    wind_speed_max_mps: float
    thunderstorm_probability: float
    snowfall_cm: float
    weather_code: Optional[str] = None
    heat_index_risk: Optional[str] = None
    storm_risk: Optional[str] = None
    visibility_risk: Optional[str] = None

@dataclass
class Scores:
    park_code: str
    start_date: str
    end_date: str
    access_score: float          # how open/accessible the park is (we'll stub this for now)
    weather_score: float         # how favorable the weather is
    risk_score: float            # aggregate risk (we'll keep simple at first)
    crowd_score: float           # how crowded we expect it to be (stub for now)
    trip_readiness_score: float  # overall readiness index 0–100
    risk_flags: List[str]        # list of strings like ["weather_risk", "access_issue"]
    notes: List[str]             # human-readable notes for later use in the UI/LLM


@dataclass
class Alert:
    alert_id: str
    park_code: str
    title: str
    category: str          # NPS category (e.g., "Alert", "Warning")
    type: str              # our normalized type: "road_closure", "fire", "flood", "general", etc.
    severity: str          # "low" | "medium" | "high"
    is_major: bool         # whether this should strongly affect access_score
    url: Optional[str] = None
    summary: Optional[str] = None
    raw_text: Optional[str] = None

@dataclass
class DocumentChunk:
    doc_id: str        # e.g., NPS article id
    chunk_id: int      # index of the chunk within the article
    text: str          # the actual chunk text
    source: str  

@dataclass
class ThingsToDoItem:
    """
    A single 'thing to do' from the NPS API for a park.
    This is especially useful for hikes/trails and key viewpoints.

    We keep it simple and text-centric so it plays nicely with RAG.
    """
    park_code: str
    id: str
    title: str
    short_description: str
    listing_description: str
    long_description: str 
    url: str
    activities: List[str]
    duration_hours: Optional[float] = None
    is_trail: bool = False