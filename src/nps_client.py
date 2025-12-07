from typing import List
import requests

from .config import NPS_API_KEY
from .models import Alert

BASE_URL = "https://developer.nps.gov/api/v1"


def get_alerts_for_park(park_code: str) -> List[Alert]:
    """
    Fetch alerts for a park from the NPS API.
    If no API key is configured, return an empty list gracefully.
    """
    # If user hasn't set an API key yet, just skip alerts.
    if not NPS_API_KEY:
        # You could print one debug line if you want:
        # print("No NPS_API_KEY set; skipping NPS alerts.")
        return []

    params = {
        "parkCode": park_code,
        "api_key": NPS_API_KEY,
        "limit": 50,
    }

    resp = requests.get(f"{BASE_URL}/alerts", params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    alerts: List[Alert] = []
    for item in data.get("data", []):
        alert = Alert(
            alert_id=item.get("id", ""),
            park_code=park_code,
            title=item.get("title", ""),
            category=item.get("category", "") or "",
            type=_infer_alert_type(item),
            severity=_infer_severity(item),
            is_major=_infer_is_major(item),
            url=item.get("url") or None,
            summary=item.get("description") or None,
            raw_text=item.get("description") or None,
        )
        alerts.append(alert)

    return alerts


def _infer_alert_type(item: dict) -> str:
    """
    Basic keyword-based classifier to turn raw NPS alert into our normalized type.
    You can refine this over time.
    """
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    if "road" in text and "clos" in text:
        return "road_closure"
    if "trail" in text and "clos" in text:
        return "trail_closure"
    if "fire" in text:
        return "fire"
    if "flood" in text:
        return "flood"
    if "weather" in text or "storm" in text or "snow" in text:
        return "weather"
    return "general"


def _infer_severity(item: dict) -> str:
    """
    Very rough heuristic for severity.
    Later you can tune this based on park experience or manual labeling.
    """
    text = (item.get("title", "") + " " + item.get("description", "")).lower()
    if "closed" in text or "not accessible" in text:
        return "high"
    if "limited" in text or "delays" in text:
        return "medium"
    return "low"


def _infer_is_major(item: dict) -> bool:
    """
    Decide whether this alert should materially affect access_score.
    """
    t = _infer_alert_type(item)
    s = _infer_severity(item)
    if t in ("road_closure", "trail_closure", "fire", "flood") and s in ("medium", "high"):
        return True
    return False
