import requests
from typing import List, Dict

from .config import NPS_API_KEY


def fetch_articles_for_park(park_code: str, limit: int = 50) -> List[Dict]:
    """
    Fetch article metadata and descriptions from the NPS Articles API.
    Uses NPS_API_KEY from src.config.
    """
    if not NPS_API_KEY:
        raise ValueError("NPS_API_KEY not set! Run `export NPS_API_KEY=...` in your terminal.")

    url = "https://developer.nps.gov/api/v1/articles"
    params = {
        "parkCode": park_code,
        "api_key": NPS_API_KEY,
        "limit": limit,
    }

    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()

    return resp.json().get("data", [])
