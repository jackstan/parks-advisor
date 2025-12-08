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
