"""Minimal OpenBeta GraphQL client with area and route retrieval helpers."""

from time import sleep
from typing import Any, Dict, List, Optional

import requests


OPENBETA_ENDPOINT = "https://api.openbeta.io"

SEARCH_AREAS_QUERY = """
query SearchAreas($name: String!) {
  areas(filter: { area_name: { match: $name } }, limit: 10) {
    area_name
    uuid
    totalClimbs
    metadata {
      lat
      lng
    }
    children {
      area_name
      uuid
      totalClimbs
      metadata {
        lat
        lng
      }
    }
  }
}
"""

SEARCH_AREAS_BY_PATH_QUERY = """
query SearchAreasByPath($tokens: [String]!) {
  areas(filter: { path_tokens: { tokens: $tokens } }, sort: { totalClimbs: -1 }, limit: 12) {
    area_name
    uuid
    totalClimbs
    metadata {
      lat
      lng
    }
    children {
      area_name
      uuid
      totalClimbs
      metadata {
        lat
        lng
      }
    }
  }
}
"""

AREA_ROUTES_QUERY = """
query AreaRoutes($uuid: ID!) {
  area(uuid: $uuid) {
    area_name
    uuid
    totalClimbs
    metadata {
      lat
      lng
    }
    climbs {
      name
      length
      grades {
        yds
        french
        font
        vscale
        wi
      }
      type {
        trad
        sport
        bouldering
        deepwatersolo
        alpine
        snow
        ice
        mixed
        aid
        tr
      }
      safety
      metadata {
        lat
        lng
        left_right_index
        mp_id
        climb_id
      }
      content {
        description
        protection
        location
      }
    }
  }
}
"""

CRAGS_NEAR_QUERY = """
query CragsNear($lnglat: Point!, $minDistance: Int, $maxDistance: Int, $includeCrags: Boolean) {
  cragsNear(
    lnglat: $lnglat
    minDistance: $minDistance
    maxDistance: $maxDistance
    includeCrags: $includeCrags
  ) {
    count
    crags {
      area_name
      uuid
      totalClimbs
      metadata {
        lat
        lng
      }
    }
  }
}
"""


def run_query(query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Execute a GraphQL query against the OpenBeta API.

    Retries a small number of transient failures because the public endpoint
    occasionally returns 5xx or times out on valid requests.

    Raises:
        requests.HTTPError: When the HTTP request fails.
        RuntimeError: When the GraphQL response includes errors or malformed data.
    """
    payload = {
        "query": query,
        "variables": variables or {},
    }

    last_exception: Optional[Exception] = None
    for attempt in range(3):
        try:
            response = requests.post(OPENBETA_ENDPOINT, json=payload, timeout=25)
            response.raise_for_status()

            body = response.json()
            errors = body.get("errors")
            if errors:
                raise RuntimeError(f"OpenBeta GraphQL errors: {errors}")

            data = body.get("data")
            if data is None:
                raise RuntimeError("OpenBeta response did not include a 'data' field.")

            return data
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_exception = exc
            if attempt == 2:
                raise
            sleep(0.5 * (attempt + 1))

    if last_exception is not None:
        raise last_exception
    raise RuntimeError("OpenBeta query failed without returning data.")


def search_areas(name: str) -> List[Dict[str, Any]]:
    """Search OpenBeta areas by area name."""
    data = run_query(SEARCH_AREAS_QUERY, {"name": name})
    return data.get("areas", [])


def search_areas_by_path_tokens(tokens: List[str]) -> List[Dict[str, Any]]:
    """Search OpenBeta areas by path tokens such as a park or region name."""
    if not tokens:
        return []
    data = run_query(SEARCH_AREAS_BY_PATH_QUERY, {"tokens": tokens})
    return data.get("areas", [])


def get_area_routes(area_uuid: str) -> Dict[str, Any]:
    """Fetch a single area with route-level data."""
    data = run_query(AREA_ROUTES_QUERY, {"uuid": area_uuid})
    return data.get("area") or {}


def crags_near(
    lat: float,
    lon: float,
    min_distance: int = 0,
    max_distance: int = 200_000,
    include_crags: bool = True,
) -> List[Dict[str, Any]]:
    """Return nearby crags using OpenBeta's geographic query."""
    data = run_query(
        CRAGS_NEAR_QUERY,
        {
            "lnglat": {"lng": lon, "lat": lat},
            "minDistance": min_distance,
            "maxDistance": max_distance,
            "includeCrags": include_crags,
        },
    )
    result = data.get("cragsNear") or []
    if isinstance(result, list):
        crags: List[Dict[str, Any]] = []
        for bucket in result:
            if isinstance(bucket, dict):
                crags.extend(bucket.get("crags", []))
        return crags
    if isinstance(result, dict):
        return result.get("crags", [])
    return []
