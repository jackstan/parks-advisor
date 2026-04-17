"""Local climbing area index used to translate fuzzy user place input."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


INDEX_PATH = Path(__file__).with_name("data") / "area_index.json"
STOP_WORDS = {
    "a",
    "an",
    "around",
    "at",
    "climb",
    "climbing",
    "for",
    "from",
    "go",
    "i",
    "in",
    "me",
    "near",
    "national",
    "of",
    "outside",
    "park",
    "region",
    "state",
    "the",
    "to",
    "want",
    "county",
}


@dataclass(frozen=True)
class AreaIndexEntry:
    """A local higher-level climbing area cluster."""

    entry_id: str
    uuid: Optional[str]
    area_name: str
    parent_uuid: Optional[str]
    path: List[str]
    lat: Optional[float]
    lng: Optional[float]
    region: Optional[str]
    state: Optional[str]
    country: Optional[str]
    aliases: List[str]
    search_targets: List[str]
    cluster_type: str
    serves_origins: List[str]


@dataclass(frozen=True)
class ResolvedClimbingQuery:
    """Resolved local interpretation of a free-form climbing place query."""

    normalized_query: str
    matched_entries: List[AreaIndexEntry]
    nearby_entries: List[AreaIndexEntry]
    destination_search_targets: List[str]
    mode_hint: Optional[str]
    origin_anchor: Optional[Dict[str, Any]]


def _normalize_text(value: str) -> str:
    """Normalize text for lightweight fuzzy matching."""
    cleaned = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return " ".join(cleaned.split())


def _tokenize(value: str) -> set[str]:
    """Tokenize input and remove low-signal words."""
    return {
        token
        for token in _normalize_text(value).split()
        if token and token not in STOP_WORDS
    }


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in miles."""
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)

    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 3958.8 * c


def _load_index_rows() -> List[Dict[str, Any]]:
    """Load raw index rows from disk."""
    with INDEX_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_area_index() -> List[AreaIndexEntry]:
    """Load the local climbing area index."""
    entries: List[AreaIndexEntry] = []
    for row in _load_index_rows():
        entries.append(
            AreaIndexEntry(
                entry_id=row["entry_id"],
                uuid=row.get("uuid"),
                area_name=row["area_name"],
                parent_uuid=row.get("parent_uuid"),
                path=list(row.get("path", [])),
                lat=row.get("lat"),
                lng=row.get("lng"),
                region=row.get("region"),
                state=row.get("state"),
                country=row.get("country"),
                aliases=list(row.get("aliases", [])),
                search_targets=list(row.get("search_targets", [])),
                cluster_type=row.get("cluster_type", "destination"),
                serves_origins=list(row.get("serves_origins", [])),
            )
        )
    return entries


def find_nearby_area_clusters(
    lat: float,
    lon: float,
    max_distance_miles: float = 175.0,
    limit: int = 4,
) -> List[AreaIndexEntry]:
    """Return index entries whose centroids are near a given origin."""
    nearby: List[tuple[float, AreaIndexEntry]] = []
    for entry in load_area_index():
        if entry.lat is None or entry.lng is None:
            continue
        distance = _haversine_miles(lat, lon, entry.lat, entry.lng)
        if distance <= max_distance_miles:
            nearby.append((distance, entry))

    nearby.sort(key=lambda item: item[0])
    return [entry for _, entry in nearby[:limit]]


def _entry_score(query: str, query_tokens: set[str], entry: AreaIndexEntry) -> int:
    """Score a local index entry against the free-form query."""
    normalized_query = _normalize_text(query)
    best_score = 0

    strong_phrases = [
        entry.area_name,
        *entry.aliases,
        *entry.search_targets,
    ]
    weak_phrases = [
        *entry.serves_origins,
        *(entry.path or []),
    ]

    for phrase in strong_phrases:
        normalized_phrase = _normalize_text(phrase)
        phrase_tokens = _tokenize(phrase)

        if normalized_query == normalized_phrase:
            best_score = max(best_score, 120)
            continue

        if normalized_phrase and normalized_phrase in normalized_query:
            best_score = max(best_score, 95)

        if normalized_query and normalized_query in normalized_phrase:
            best_score = max(best_score, 85)

        overlap = len(query_tokens & phrase_tokens)
        if overlap:
            overlap_score = overlap * 20 + int(25 * overlap / max(len(phrase_tokens), 1))
            best_score = max(best_score, overlap_score)

    for phrase in weak_phrases:
        normalized_phrase = _normalize_text(phrase)
        phrase_tokens = _tokenize(phrase)

        if normalized_phrase and normalized_phrase in normalized_query:
            best_score = max(best_score, 55)

        overlap = len(query_tokens & phrase_tokens)
        if overlap:
            overlap_score = overlap * 10 + int(15 * overlap / max(len(phrase_tokens), 1))
            best_score = max(best_score, overlap_score)

    if entry.region and _normalize_text(entry.region) in normalized_query:
        best_score = max(best_score, 50)

    return best_score


def _has_explicit_entry_match(query: str, entry: AreaIndexEntry) -> bool:
    """True when the query directly references the entry rather than only a served origin."""
    normalized_query = _normalize_text(query)
    explicit_phrases = [entry.area_name, *entry.aliases, *entry.search_targets]
    for phrase in explicit_phrases:
        normalized_phrase = _normalize_text(phrase)
        if not normalized_phrase:
            continue
        if normalized_query == normalized_phrase or normalized_phrase in normalized_query:
            return True
    return False


def _dedupe_strings(values: List[str]) -> List[str]:
    """Preserve order while removing duplicate strings."""
    deduped: List[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(value)
    return deduped


def resolve_climbing_query(
    query: str,
    geocode_result: Optional[Dict[str, Any]] = None,
) -> ResolvedClimbingQuery:
    """
    Resolve a free-form climbing place query against the local area index.

    This returns stronger search targets for OpenBeta and, when possible,
    a geographic anchor for origin-style phrasing such as "north of San Francisco".
    """
    entries = load_area_index()
    query_tokens = _tokenize(query)
    scored_entries = [
        (score, entry)
        for entry in entries
        for score in [_entry_score(query, query_tokens, entry)]
        if score >= 45
    ]
    scored_entries.sort(key=lambda item: item[0], reverse=True)
    top_score = scored_entries[0][0] if scored_entries else 0
    matched_entries = [
        entry
        for score, entry in scored_entries
        if score >= max(60, top_score - 25)
    ][:3]

    nearby_entries: List[AreaIndexEntry] = []
    if geocode_result is not None:
        try:
            nearby_entries = find_nearby_area_clusters(
                float(geocode_result["lat"]),
                float(geocode_result["lon"]),
            )
        except (KeyError, TypeError, ValueError):
            nearby_entries = []

    destination_search_targets: List[str] = []
    for entry in matched_entries:
        destination_search_targets.extend(entry.search_targets or [entry.area_name])

    if not destination_search_targets and nearby_entries:
        for entry in nearby_entries:
            if entry.cluster_type != "origin_cluster":
                destination_search_targets.extend(entry.search_targets or [entry.area_name])

    mode_hint: Optional[str] = None
    origin_anchor: Optional[Dict[str, Any]] = None
    top_entry = matched_entries[0] if matched_entries else None

    if (
        top_entry is not None
        and top_entry.cluster_type == "origin_cluster"
        and top_entry.lat is not None
        and top_entry.lng is not None
        and _has_explicit_entry_match(query, top_entry)
    ):
        mode_hint = "origin"
        origin_anchor = {
            "label": top_entry.area_name,
            "lat": top_entry.lat,
            "lon": top_entry.lng,
        }
    elif top_entry is not None and (
        top_entry.cluster_type != "origin_cluster" or _has_explicit_entry_match(query, top_entry)
    ):
        mode_hint = "destination"

    if mode_hint is None and nearby_entries:
        mode_hint = "origin"

    return ResolvedClimbingQuery(
        normalized_query=_normalize_text(query),
        matched_entries=matched_entries,
        nearby_entries=nearby_entries,
        destination_search_targets=_dedupe_strings(destination_search_targets or [query]),
        mode_hint=mode_hint,
        origin_anchor=origin_anchor,
    )
