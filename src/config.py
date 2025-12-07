
import os

# Read NPS_API_KEY directly from the environment.
# You will set this in your terminal with: export NPS_API_KEY="..."
NPS_API_KEY = os.getenv("NPS_API_KEY", "")

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

PARKS = {
    "yose": YOSEMITE,
}
