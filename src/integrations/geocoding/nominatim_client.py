"""Minimal Nominatim geocoding client for origin search."""

from typing import Any, Dict, Optional

import requests


NOMINATIM_SEARCH_ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Sendable/0.1 (local development)"


def geocode_place(query: str) -> Optional[Dict[str, Any]]:
    """
    Geocode a place/origin query using Nominatim.

    Returns the top result or None when no result is found.
    """
    response = requests.get(
        NOMINATIM_SEARCH_ENDPOINT,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
            "addressdetails": 1,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()

    results = response.json()
    if not results:
        return None
    return results[0]
