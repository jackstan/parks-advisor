import requests
from typing import List, Optional

from .config import NPS_API_KEY
from .models import ThingsToDoItem


BASE_URL = "https://developer.nps.gov/api/v1/thingstodo"


def _parse_duration_hours(item: dict) -> Optional[float]:
    """
    NPS ThingsToDo duration fields can be messy.
    We'll try to extract a rough number of hours if present.
    """
    # Example fields in the API: "duration", "durationUnit"
    duration = item.get("duration")
    unit = item.get("durationUnit", "").lower()

    if duration is None:
        return None

    try:
        value = float(duration)
    except (TypeError, ValueError):
        return None

    if unit in ("hour", "hours"):
        return value
    if unit in ("minute", "minutes"):
        return value / 60.0

    # Unknown / weird unit — leave as None for now
    return None


def _is_trail_like(item: dict) -> bool:
    """
    Heuristic: decide if this item is likely a trail/hike.
    """
    title = (item.get("title") or "").lower()
    # Some APIs use "activities" with names like "Hiking", "Backpacking", etc.
    activities = [a.get("name", "").lower() for a in item.get("activities", [])]

    keywords = ("hike", "hiking", "trail", "walk", "walking")
    if any(k in title for k in keywords):
        return True
    if any(any(k in act for k in keywords) for act in activities):
        return True
    return False


def get_things_to_do_for_park(park_code: str, limit: int = 50) -> List[ThingsToDoItem]:
    """
    Fetch "Things to Do" for a given park using the NPS API.

    Docs: /api/v1/thingstodo?parkCode=YOSE&api_key=...

    Returns a list of ThingsToDoItem objects.
    """
    if not NPS_API_KEY:
        raise RuntimeError("NPS_API_KEY is not set. Add it to your .env.")

    params = {
        "parkCode": park_code,
        "api_key": NPS_API_KEY,
        "limit": limit,
    }

    resp = requests.get(BASE_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    items: List[ThingsToDoItem] = []

    for raw in data.get("data", []):
        title = raw.get("title") or ""
        short_desc = raw.get("shortDescription") or ""
        list_desc = raw.get("listingDescription") or ""
        long_desc = raw.get("longDescription") or ""
        url = raw.get("url") or ""
        activities = [a.get("name", "") for a in raw.get("activities", [])]

        duration_hours = _parse_duration_hours(raw)
        is_trail = _is_trail_like(raw)

        items.append(
            ThingsToDoItem(
                park_code=park_code,
                id=raw.get("id") or "",
                title=title,
                short_description=short_desc,
                listing_description=list_desc,
                long_description=long_desc,
                url=url,
                activities=activities,
                duration_hours=duration_hours,
                is_trail=is_trail,
            )
        )

    print(f"[DEBUG things_to_do] {park_code} -> {len(items)} ThingsToDo items")
    if items:
        print(f"[DEBUG things_to_do] First item: {items[0].title!r}, activities={items[0].activities}")

    return items
