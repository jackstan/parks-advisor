import os
from pathlib import Path
from typing import Dict, Any

import requests
from dotenv import load_dotenv

# Resolve project root (one level up from src/)
ROOT_DIR = Path(__file__).resolve().parents[1]

# Load .env from project root
load_dotenv(ROOT_DIR / ".env")

# API keys
NPS_API_KEY = os.getenv("NPS_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Default Yosemite entry (good fallback & example) -----------------------

YOSEMITE = {
    "park_code": "yose",
    "name": "Yosemite National Park",
    "states": ["CA"],
    "type": "national_park",
    "lat": 37.8651,
    "lon": -119.5383,
    "timezone": "America/Los_Angeles",
    "elevation_band": "mountain",
    "primary_activities": ["hiking", "climbing", "sightseeing"],
    "nps_url": "https://www.nps.gov/yose/index.htm",
    "season_notes": "High snow at high elevations until early summer; spring runoff; summer heat in valley.",
}


def _parse_lat_lon(lat_long_str: str):
    """
    NPS parks API returns 'latLong' like: 'lat:37.8651, long:-119.5383'.
    This helper extracts floats or returns (None, None) if parsing fails.
    """
    if not lat_long_str:
        return None, None

    try:
        parts = lat_long_str.split(",")
        lat_part = parts[0].strip()
        lon_part = parts[1].strip()

        lat_val = float(lat_part.split(":")[1])
        lon_val = float(lon_part.split(":")[1])
        return lat_val, lon_val
    except Exception:
        return None, None


def _load_parks_from_nps() -> Dict[str, Dict[str, Any]]:
    """
    Load all 'National Park' units from the NPS /parks endpoint and
    return a dict keyed by parkCode.

    We keep only basic fields needed by the rest of the app:
    - park_code
    - name
    - states
    - type
    - lat
    - lon
    - nps_url
    """
    parks: Dict[str, Dict[str, Any]] = {}

    if not NPS_API_KEY:
        print("[config] NPS_API_KEY not set; using only built-in Yosemite config.")
        return parks

    url = "https://developer.nps.gov/api/v1/parks"
    params = {
        "designation": "National Park",
        "limit": 500,
        "api_key": NPS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[config] Failed to load parks from NPS API: {e}")
        return parks

    for item in data.get("data", []):
        park_code = item.get("parkCode")
        if not park_code:
            continue

        name = item.get("fullName") or item.get("name") or park_code
        states_str = item.get("states", "")  # e.g. "CA" or "CA,NV"
        states = [s.strip() for s in states_str.split(",") if s.strip()]
        lat, lon = _parse_lat_lon(item.get("latLong", ""))

        if lat is None or lon is None:
            # Skip parks without usable coordinates (needed for weather)
            continue

        parks[park_code] = {
            "park_code": park_code,
            "name": name,
            "states": states,
            "type": "national_park",
            "lat": lat,
            "lon": lon,
            # Timezone isn't provided by NPS; Open-Meteo uses timezone=auto,
            # so this is mostly cosmetic. Default to US Pacific for now or leave out.
            "timezone": "America/Los_Angeles",
            "primary_activities": [],  # could be filled from NPS 'activities' later
            "nps_url": item.get("url") or "",
            "season_notes": "",
        }

    print(f"[config] Loaded {len(parks)} national parks from NPS API.")
    return parks


# Base PARKS dict: Yosemite + any loaded from NPS
PARKS: Dict[str, Dict[str, Any]] = {"yose": YOSEMITE}
PARKS.update(_load_parks_from_nps())

# --- Climbing areas (v1: Red River Gorge, Index, Bishop) ---------------

CLIMBING_AREAS: Dict[str, Dict[str, Any]] = {
    "rrg": {
        "area_id": "rrg",
        "name": "Red River Gorge",
        "state": "KY",
        "lat": 38.5,
        "lon": -83.7,
        "elevation_ft": 800,
        "timezone": "America/Chicago",
        "primary_rock_type": "sandstone",
        "primary_climb_types": ["sport", "trad"],
        "grade_range": "5.6-5.12c",
        "approach_difficulty": "moderate",
        "is_established": True,
        "permit_required": False,
        "best_seasons": ["spring", "fall"],
        "crowd_tendency": "high",
        "typical_wetness_after_rain_hours": 24,
        "typical_freeze_temp_f": 32,
    },
    "index": {
        "area_id": "index",
        "name": "Index",
        "state": "WA",
        "lat": 47.85,
        "lon": -121.80,
        "elevation_ft": 2000,
        "timezone": "America/Los_Angeles",
        "primary_rock_type": "granite",
        "primary_climb_types": ["trad"],
        "grade_range": "5.7-5.11d",
        "approach_difficulty": "moderate",
        "is_established": True,
        "permit_required": False,
        "best_seasons": ["summer", "fall"],
        "crowd_tendency": "low",
        "typical_wetness_after_rain_hours": 12,
        "typical_freeze_temp_f": 32,
    },
    "bishop": {
        "area_id": "bishop",
        "name": "Bishop",
        "state": "CA",
        "lat": 37.37,
        "lon": -118.39,
        "elevation_ft": 4000,
        "timezone": "America/Los_Angeles",
        "primary_rock_type": "granite",
        "primary_climb_types": ["trad", "boulder"],
        "grade_range": "5.8-5.13b",
        "approach_difficulty": "easy",
        "is_established": True,
        "permit_required": False,
        "best_seasons": ["spring", "fall"],
        "crowd_tendency": "high",
        "typical_wetness_after_rain_hours": 6,
        "typical_freeze_temp_f": 28,
    },
}

# --- Factory functions for objective-oriented access ---------------------

def get_objective_location(domain: str, location_id: str) -> Dict[str, Any]:
    """
    Get location metadata for an objective.
    
    Args:
        domain: "hiking", "climbing", "skiing", etc.
        location_id: location identifier (park code, crag ID, etc.)
    
    Returns:
        Dict with lat, lon, name, and domain-specific metadata
    
    Raises:
        KeyError if location not found
    """
    if domain == "hiking":
        if location_id not in PARKS:
            raise KeyError(f"Park '{location_id}' not found in PARKS config")
        return PARKS[location_id]
    elif domain == "climbing":
        if location_id not in CLIMBING_AREAS:
            raise KeyError(f"Climbing area '{location_id}' not found in CLIMBING_AREAS config")
        return CLIMBING_AREAS[location_id]
    else:
        raise ValueError(f"Unknown domain: {domain}")


def get_locations_by_domain(domain: str) -> Dict[str, str]:
    """
    Get all available locations for a domain.
    
    Useful for UI dropdown/selector.
    
    Returns:
        Dict mapping location_id → location_name
    """
    if domain == "hiking":
        return {code: park.get("name", code) for code, park in PARKS.items()}
    elif domain == "climbing":
        return {code: area.get("name", code) for code, area in CLIMBING_AREAS.items()}
    else:
        raise ValueError(f"Unknown domain: {domain}")

