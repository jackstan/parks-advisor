"""
Planning orchestrator: the main entry point for objective planning.

This module implements a deterministic planner that:
1. Generates candidate objectives matching user constraints
2. Evaluates each candidate (weather, scoring, LLM context)
3. Ranks and selects primary + backup
4. Generates day plans and recommendation
"""

from typing import List, Dict, Any, Tuple, Optional
import logging

from ..domain.objective_models import Objective, UserConstraints
from ..domain.recommendation_models import (
    RecommendationRequest,
    ObjectiveCandidate,
    PlannerRecommendation,
    DayPlan,
    MapPoint,
    RouteOption,
)
from ..models import WeatherDay
from ..integrations.weather import get_weather_for_location
from ..integrations.climbing import (
    crags_near,
    get_area_routes,
    resolve_climbing_query,
    search_areas,
    search_areas_by_path_tokens,
)
from ..integrations.geocoding import geocode_place
from ..adapters import get_adapter

logger = logging.getLogger(__name__)


# --- Candidate Generation ---------------------------------------------------------------

def _normalize_name(value: str) -> str:
    """Normalize a name for lightweight matching."""
    return "".join(ch.lower() for ch in value if ch.isalnum())


def _yds_to_numeric(grade: Optional[str]) -> Optional[float]:
    """Convert a simple Yosemite Decimal grade to a sortable float."""
    if not grade:
        return None

    normalized = grade.strip().lower()
    if not normalized.startswith("5."):
        return None

    letter_bonus = {"a": 0.0, "b": 0.1, "c": 0.2, "d": 0.3, "+": 0.15}
    numeric = normalized[2:]
    number_chars = []
    suffix = ""

    for char in numeric:
        if char.isdigit():
            number_chars.append(char)
        else:
            suffix = char
            break

    if not number_chars:
        return None

    return float("".join(number_chars)) + letter_bonus.get(suffix, 0.0)


def _parse_length_ft(length_value: Any) -> Optional[int]:
    """Normalize OpenBeta route length into integer feet where possible."""
    if length_value is None:
        return None
    try:
        length = int(length_value)
    except (TypeError, ValueError):
        return None
    return length if length > 0 else None


def _grade_rank(
    grade: Optional[str],
    request: RecommendationRequest,
) -> tuple[int, float]:
    """
    Rank a route grade against the requested band.

    Lower tuple values are better.
    """
    route_grade = _yds_to_numeric(grade)
    if route_grade is None:
        return (2, 999.0)

    requested_min = _yds_to_numeric(request.grade_min)
    requested_max = _yds_to_numeric(request.grade_max)

    if requested_min is not None and requested_max is not None:
        if requested_min <= route_grade <= requested_max:
            midpoint = (requested_min + requested_max) / 2
            return (0, abs(route_grade - midpoint))
        if route_grade < requested_min:
            return (1, requested_min - route_grade)
        return (1, route_grade - requested_max)

    if requested_max is not None:
        return (0, abs(route_grade - requested_max))

    if requested_min is not None:
        return (0, abs(route_grade - requested_min))

    return (1, 0.0)


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance in miles between two lat/lon points."""
    from math import asin, cos, radians, sin, sqrt

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)

    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 3958.8 * c


def _route_types_from_openbeta(route_type: Dict[str, Any]) -> List[str]:
    """Flatten the OpenBeta route type object into a list of active flags."""
    return [name for name, enabled in (route_type or {}).items() if enabled]


def _select_best_openbeta_area(
    search_term: str,
    areas: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Pick the most relevant OpenBeta area result.

    Prefer:
    1. exact name matches
    2. results with coordinates
    3. results with children (often a parent area)
    """
    if not areas:
        return None

    normalized_search = _normalize_name(search_term)

    def sort_key(area: Dict[str, Any]) -> Tuple[int, int, int]:
        area_name = area.get("area_name", "")
        metadata = area.get("metadata") or {}
        has_coords = 1 if metadata.get("lat") is not None and metadata.get("lng") is not None else 0
        exact_match = 1 if _normalize_name(area_name) == normalized_search else 0
        child_count = len(area.get("children") or [])
        return (exact_match, has_coords, child_count)

    return max(areas, key=sort_key)

def _is_origin_like_geocode(geocode_result: Optional[Dict[str, Any]]) -> bool:
    """Heuristic: true when the geocoded result looks like a city/origin query."""
    if not geocode_result:
        return False

    addresstype = str(geocode_result.get("addresstype", "")).lower()
    place_type = str(geocode_result.get("type", "")).lower()

    origin_types = {
        "city",
        "town",
        "village",
        "municipality",
        "county",
        "administrative",
        "suburb",
        "hamlet",
    }

    return addresstype in origin_types or place_type in origin_types


def _is_strong_destination_match(search_term: str, selected_area: Optional[Dict[str, Any]]) -> bool:
    """Heuristic: true when the area result looks like a real climbing destination."""
    if not selected_area:
        return False

    normalized_search = _normalize_name(search_term)
    area_name = selected_area.get("area_name", "")
    exact_match = _normalize_name(area_name) == normalized_search
    total_climbs = int(selected_area.get("totalClimbs") or 0)
    child_count = len(selected_area.get("children") or [])
    return exact_match or total_climbs >= 50 or child_count >= 5


def _merge_climbing_metadata(
    source_area: Dict[str, Any],
    climbing_catalog: Dict[str, Dict[str, Any]],
    requested_term: str,
    *,
    parent_area: Optional[Dict[str, Any]] = None,
    distance_miles: Optional[float] = None,
) -> Dict[str, Any]:
    """Merge OpenBeta area data with any local climbing metadata when names align."""
    source_name = source_area.get("area_name", requested_term)
    source_uuid = source_area.get("uuid")
    metadata = source_area.get("metadata") or {}
    normalized_source_name = _normalize_name(source_name)

    local_meta: Dict[str, Any] = {}
    for local_id, candidate_meta in climbing_catalog.items():
        candidate_name = candidate_meta.get("name", "")
        if _normalize_name(candidate_name) == normalized_source_name or local_id == requested_term:
            local_meta = dict(candidate_meta)
            local_meta["catalog_id"] = local_id
            break

    merged_meta = dict(local_meta)
    merged_meta.update(
        {
            "area_id": local_meta.get("area_id", source_uuid or requested_term),
            "name": source_name,
            "lat": metadata.get("lat", local_meta.get("lat")),
            "lon": metadata.get("lng", local_meta.get("lon")),
            "openbeta_uuid": source_uuid,
            "total_climbs": source_area.get("totalClimbs"),
            "source_name": "openbeta",
        }
    )

    if parent_area is not None:
        merged_meta["parent_area_name"] = parent_area.get("area_name")
        merged_meta["parent_area_uuid"] = parent_area.get("uuid")

    if distance_miles is not None:
        merged_meta["distance_miles"] = round(distance_miles, 1)

    if not merged_meta.get("timezone"):
        merged_meta["timezone"] = "America/Los_Angeles"

    return merged_meta


def _fetch_route_options_for_area(
    area: Dict[str, Any],
    request: RecommendationRequest,
) -> List[RouteOption]:
    """
    Fetch and normalize route-level options for an area.

    This is intentionally best-effort because some larger OpenBeta area
    expansions are slow or intermittently fail.
    """
    area_uuid = area.get("uuid")
    area_name = area.get("area_name", "Unknown Area")
    if not area_uuid:
        return []

    try:
        area_with_routes = get_area_routes(area_uuid)
    except Exception as exc:
        logger.warning(f"OpenBeta route fetch failed for '{area_name}' ({area_uuid}): {exc}")
        return []

    route_options: List[RouteOption] = []
    for climb in area_with_routes.get("climbs") or []:
        climb_meta = climb.get("metadata") or {}
        grades = climb.get("grades") or {}
        route_type = climb.get("type") or {}

        route_options.append(
            RouteOption(
                route_id=str(climb_meta.get("climb_id") or climb_meta.get("mp_id") or climb.get("name")),
                name=climb.get("name", "Unnamed Route"),
                area_name=area_name,
                parent_area_name=area.get("parent_area_name"),
                lat=climb_meta.get("lat"),
                lon=climb_meta.get("lng"),
                grade=grades.get("yds") or grades.get("french") or grades.get("font") or grades.get("vscale") or grades.get("wi"),
                length_ft=_parse_length_ft(climb.get("length")),
                route_types=_route_types_from_openbeta(route_type),
                safety=climb.get("safety"),
                left_right_index=climb_meta.get("left_right_index"),
                source_route_id=climb_meta.get("mp_id"),
            )
        )

    route_options.sort(
        key=lambda route: (
            _grade_rank(route.grade, request),
            route.left_right_index if route.left_right_index is not None else 9999,
            route.name.lower(),
        )
    )
    return route_options[:8]


def _build_climbing_candidate(
    request: RecommendationRequest,
    objective_location_id: str,
    crag_meta: Dict[str, Any],
    route_options: List[RouteOption],
    source_reason: str,
) -> ObjectiveCandidate:
    """Create an ObjectiveCandidate from enriched climbing area and route data."""
    top_route_descriptions = [
        f"{route.name} ({route.grade})" if route.grade else route.name
        for route in route_options[:3]
    ]
    match_reason = source_reason
    if top_route_descriptions:
        match_reason = f"{source_reason} Route options: {', '.join(top_route_descriptions)}."

    objective = Objective(
        objective_id=f"climb_{objective_location_id}",
        location_id=objective_location_id,
        location_type="climbing_area",
        domain="climbing",
        start_date=request.start_date,
        end_date=request.end_date,
        constraints=UserConstraints(
            max_duration_hours=request.max_duration_hours,
            max_approach_minutes=request.max_approach_minutes,
            commitment_level=request.commitment_level,
            skill_level=request.skill_level,
            partner_count=request.partner_count,
            custom_prefs={
                "grade_min": request.grade_min,
                "grade_max": request.grade_max,
                "grade_target": request.grade_max or request.grade_min,
                "resolved_location_name": crag_meta.get("name"),
                "resolved_climb_types": crag_meta.get("primary_climb_types", []),
                "resolved_grade_range": crag_meta.get("grade_range"),
            },
        ),
        description=request.custom_notes,
    )

    return ObjectiveCandidate(
        candidate_id=f"candidate_climb_{objective_location_id}",
        objective=objective,
        location_name=crag_meta["name"],
        location_metadata=crag_meta,
        route_options=route_options,
        match_reason=match_reason,
        location_coordinates={
            "lat": float(crag_meta["lat"]),
            "lon": float(crag_meta["lon"]),
        },
    )


def _generate_destination_candidates(
    request: RecommendationRequest,
    search_term: str,
    climbing_catalog: Dict[str, Dict[str, Any]],
    search_targets: Optional[List[str]] = None,
    local_resolution_reason: Optional[str] = None,
) -> List[ObjectiveCandidate]:
    """Generate route-enriched climbing candidates for a destination search."""
    candidates: List[ObjectiveCandidate] = []

    area_results: List[Dict[str, Any]] = []
    targets_to_check = []
    for target in (search_targets or []) + [search_term]:
        if target not in targets_to_check:
            targets_to_check.append(target)

    for target in targets_to_check[:4]:
        try:
            area_results.extend(search_areas(target))
        except Exception as exc:
            logger.warning(f"OpenBeta destination area search failed for '{target}': {exc}")

        try:
            path_results = search_areas_by_path_tokens([target])
            existing_ids = {area.get("uuid") for area in area_results}
            for result in path_results:
                if result.get("uuid") not in existing_ids:
                    area_results.append(result)
        except Exception as exc:
            logger.warning(f"OpenBeta path-token search failed for '{target}': {exc}")

    selection_term = (search_targets or [search_term])[0]
    selected_area = _select_best_openbeta_area(selection_term, area_results)
    if selected_area is None:
        return candidates

    child_areas = []
    for child in selected_area.get("children") or []:
        metadata = child.get("metadata") or {}
        if metadata.get("lat") is None or metadata.get("lng") is None:
            continue
        child_copy = dict(child)
        child_copy["parent_area_name"] = selected_area.get("area_name")
        child_areas.append(child_copy)

    if not child_areas:
        child_areas = [selected_area]

    child_areas.sort(
        key=lambda area: (
            0 if 1 <= int(area.get("totalClimbs") or 0) <= 60 else 1,
            -int(area.get("totalClimbs") or 0),
        )
    )

    for child in child_areas[:12]:
        route_options = _fetch_route_options_for_area(child, request)
        if not route_options:
            continue

        crag_meta = _merge_climbing_metadata(
            child,
            climbing_catalog,
            search_term,
            parent_area=selected_area,
        )
        candidate = _build_climbing_candidate(
            request,
            objective_location_id=crag_meta.get("catalog_id") or child.get("uuid") or crag_meta["name"],
            crag_meta=crag_meta,
            route_options=route_options,
            source_reason=(
                f"{local_resolution_reason} "
                if local_resolution_reason
                else ""
            ) + f"Destination search for {selected_area.get('area_name', search_term)} resolved to {child.get('area_name', 'sub-area')}.",
        )
        candidates.append(candidate)

    return candidates


def _generate_origin_candidates(
    request: RecommendationRequest,
    origin_term: str,
    climbing_catalog: Dict[str, Dict[str, Any]],
    origin_anchor: Optional[Dict[str, Any]] = None,
    nearby_cluster_targets: Optional[List[str]] = None,
) -> List[ObjectiveCandidate]:
    """Generate route-enriched climbing candidates near a geocoded origin."""
    if origin_anchor is not None:
        origin_lat = float(origin_anchor["lat"])
        origin_lon = float(origin_anchor["lon"])
        origin_label = str(origin_anchor.get("label") or origin_term)
    else:
        geocode_result = geocode_place(origin_term)
        if geocode_result is None:
            return []
        origin_lat = float(geocode_result["lat"])
        origin_lon = float(geocode_result["lon"])
        origin_label = origin_term

    try:
        nearby_crags = crags_near(origin_lat, origin_lon, max_distance=200_000, include_crags=True)
    except Exception as exc:
        logger.warning(f"OpenBeta nearby crag search failed for '{origin_term}': {exc}")
        return []

    ranked_crags: List[Tuple[float, Dict[str, Any]]] = []
    for crag in nearby_crags:
        metadata = crag.get("metadata") or {}
        lat = metadata.get("lat")
        lon = metadata.get("lng")
        if lat is None or lon is None:
            continue
        distance_miles = _haversine_miles(origin_lat, origin_lon, float(lat), float(lon))
        ranked_crags.append((distance_miles, crag))

    ranked_crags.sort(key=lambda item: (item[0], -int(item[1].get("totalClimbs") or 0)))

    candidates: List[ObjectiveCandidate] = []
    for distance_miles, crag in ranked_crags[:20]:
        route_options = _fetch_route_options_for_area(crag, request)
        if not route_options:
            continue

        crag_meta = _merge_climbing_metadata(
            crag,
            climbing_catalog,
            origin_term,
            distance_miles=distance_miles,
        )
        candidate = _build_climbing_candidate(
            request,
            objective_location_id=crag_meta.get("catalog_id") or crag.get("uuid") or crag_meta["name"],
            crag_meta=crag_meta,
            route_options=route_options,
            source_reason=f"Origin search from {origin_label} surfaced a nearby climbing option about {distance_miles:.0f} miles away.",
        )
        candidates.append(candidate)
        if len(candidates) >= 8:
            break

    if len(candidates) < 3 and nearby_cluster_targets:
        for cluster_target in nearby_cluster_targets[:3]:
            extra_candidates = _generate_destination_candidates(
                request,
                cluster_target,
                climbing_catalog,
                search_targets=[cluster_target],
                local_resolution_reason=f"Local area index translated {origin_term} toward the {cluster_target} cluster.",
            )
            for candidate in extra_candidates:
                if candidate.candidate_id not in {existing.candidate_id for existing in candidates}:
                    candidates.append(candidate)
                if len(candidates) >= 8:
                    break
            if len(candidates) >= 8:
                break

    return candidates

def _generate_climbing_candidates(
    request: RecommendationRequest,
    climbing_catalog: Dict[str, Dict[str, Any]],
) -> List[ObjectiveCandidate]:
    """
    Generate candidate climbing objectives for either destination or origin search.

    Destination mode:
    - resolve a destination to relevant child crags/sub-areas
    - fetch route options for those crags

    Origin mode:
    - geocode the origin
    - find nearby crags
    - fetch route options for the nearby crags
    """
    candidate_crags = []
    
    if request.location_ids:
        crags_to_check = request.location_ids
    else:
        crags_to_check = list(climbing_catalog.keys())
    
    for requested_id in crags_to_check:
        try:
            geocode_result = geocode_place(requested_id)
        except Exception as exc:
            logger.warning(f"Geocode lookup failed for '{requested_id}': {exc}")
            geocode_result = None

        local_resolution = resolve_climbing_query(requested_id, geocode_result)

        try:
            area_results = search_areas(requested_id)
        except Exception as exc:
            logger.warning(f"OpenBeta area lookup failed for '{requested_id}': {exc}")
            area_results = []

        selected_area = _select_best_openbeta_area(requested_id, area_results)
        local_reason: Optional[str] = None
        if local_resolution.matched_entries:
            local_reason = (
                f"Local area index matched '{requested_id}' to "
                f"{local_resolution.matched_entries[0].area_name}."
            )

        should_use_origin = (
            local_resolution.mode_hint == "origin"
            or (_is_origin_like_geocode(geocode_result) and not _is_strong_destination_match(requested_id, selected_area))
        )

        if should_use_origin:
            cluster_targets = [
                entry.area_name
                for entry in local_resolution.nearby_entries
            ]
            if local_resolution.matched_entries:
                cluster_targets.extend(entry.area_name for entry in local_resolution.matched_entries)
            generated = _generate_origin_candidates(
                request,
                requested_id,
                climbing_catalog,
                origin_anchor=local_resolution.origin_anchor,
                nearby_cluster_targets=cluster_targets,
            )
        else:
            generated = _generate_destination_candidates(
                request,
                requested_id,
                climbing_catalog,
                search_targets=local_resolution.destination_search_targets,
                local_resolution_reason=local_reason,
            )
            if not generated and geocode_result is not None:
                cluster_targets = [entry.area_name for entry in local_resolution.nearby_entries]
                generated = _generate_origin_candidates(
                    request,
                    requested_id,
                    climbing_catalog,
                    origin_anchor=local_resolution.origin_anchor,
                    nearby_cluster_targets=cluster_targets,
                )

        candidate_crags.extend(generated)
    
    deduped_candidates: List[ObjectiveCandidate] = []
    seen_ids: set[str] = set()
    for candidate in candidate_crags:
        dedupe_key = candidate.candidate_id
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped_candidates.append(candidate)

    return deduped_candidates


def _generate_hiking_candidates(
    request: RecommendationRequest,
    hiking_catalog: Dict[str, Dict[str, Any]],
) -> List[ObjectiveCandidate]:
    """
    Generate candidate parks for hiking.
    For v1, just return Yosemite as default.
    """
    candidate_parks = []
    
    if request.location_ids:
        parks_to_check = request.location_ids
    else:
        parks_to_check = list(hiking_catalog.keys()) or ["yose"]
    
    for park_code in parks_to_check:
        if park_code not in hiking_catalog:
            logger.warning(f"Park '{park_code}' not found; skipping")
            continue
        
        park_meta = hiking_catalog[park_code]
        
        objective = Objective(
            objective_id=f"hike_{park_code}",
            location_id=park_code,
            location_type="national_park",
            domain="hiking",
            start_date=request.start_date,
            end_date=request.end_date,
            constraints=UserConstraints(
                max_duration_hours=request.max_duration_hours,
                max_approach_minutes=request.max_approach_minutes,
                skill_level=request.skill_level,
            ),
            description=request.custom_notes,
        )
        
        candidate = ObjectiveCandidate(
            candidate_id=f"candidate_hike_{park_code}",
            objective=objective,
            location_name=park_meta["name"],
            location_metadata=park_meta,
            match_reason="National park matching your hiking preferences",
            location_coordinates={
                "lat": float(park_meta["lat"]),
                "lon": float(park_meta["lon"]),
            },
        )
        
        candidate_parks.append(candidate)
    
    return candidate_parks


def generate_candidates(request: RecommendationRequest) -> List[ObjectiveCandidate]:
    """
    Generate candidate objectives matching user constraints.
    
    Domain-aware: calls appropriate generator for climbing, hiking, skiing.
    """
    adapter = get_adapter(request.domain)
    location_catalog = adapter.get_location_catalog()

    if request.domain == "climbing":
        return _generate_climbing_candidates(request, location_catalog)
    elif request.domain == "hiking":
        return _generate_hiking_candidates(request, location_catalog)
    else:
        raise ValueError(f"Unknown domain: {request.domain}")


# --- Candidate Evaluation ---------------------------------------------------------------

def evaluate_candidate(candidate: ObjectiveCandidate) -> ObjectiveCandidate:
    """
    Evaluate a single candidate objective.
    
    Fetches weather, alerts, runs scoring, gets LLM context.
    Mutates candidate to fill in scores and metadata.
    """
    objective = candidate.objective
    location_meta = candidate.location_metadata
    
    try:
        adapter = get_adapter(objective.domain)

        # 1. Fetch weather
        lat = location_meta.get("lat")
        lon = location_meta.get("lon")
        if lat is None or lon is None:
            logger.warning(f"Location {objective.location_id} missing lat/lon; skipping evaluation")
            return candidate
        
        weather_days = get_weather_for_location(
            lat=float(lat),
            lon=float(lon),
            start_date=objective.start_date,
            end_date=objective.end_date,
            location_id=objective.location_id,
        )
        candidate.weather_days = weather_days
        
        # 2. Fetch alerts
        alerts = []
        alert_provider = adapter.get_alert_provider(objective)
        if alert_provider is not None:
            alerts = alert_provider.get_alerts(objective.location_id)
        
        # 3. Compute scores with the domain adapter
        context = {
            "objective": objective,
            "weather": weather_days,
            "alerts": alerts,
            "rag_chunks": [],
            "location_metadata": location_meta,
            "content_providers": adapter.get_content_providers(objective),
        }
        
        scores = adapter.compute_scores(objective, weather_days, context)
        candidate.scores = scores
        candidate.overall_sendability_score = scores.trip_readiness_score
        candidate.selection_reason = _build_selection_reason(candidate)
        if not candidate.location_coordinates:
            candidate.location_coordinates = _extract_coordinates(location_meta)
        if "bounds" in location_meta:
            candidate.area_bounds = location_meta.get("bounds")
        
        logger.info(f"Evaluated {candidate.location_name}: score={candidate.overall_sendability_score}")
        
    except Exception as e:
        logger.error(f"Failed to evaluate candidate {candidate.candidate_id}: {e}")
        candidate.overall_sendability_score = 50.0  # Default neutral score on error
    
    return candidate


def evaluate_candidates(candidates: List[ObjectiveCandidate]) -> List[ObjectiveCandidate]:
    """
    Evaluate all candidates (fetch weather, score, etc).
    Returns evaluated candidates sorted by score (highest first).
    """
    evaluated = []
    for candidate in candidates:
        evaluated.append(evaluate_candidate(candidate))
    
    # Sort by overall sendability score (highest first)
    evaluated.sort(key=lambda c: c.overall_sendability_score, reverse=True)
    
    return evaluated


# --- Ranking and Selection ---------------------------------------------------------------

def rank_candidates(candidates: List[ObjectiveCandidate]) -> List[ObjectiveCandidate]:
    """
    Rank candidates by overall sendability score.
    Assumes candidates are already evaluated.
    """
    ranked = sorted(candidates, key=lambda c: c.overall_sendability_score, reverse=True)
    for i, candidate in enumerate(ranked, 1):
        candidate.rank = i
    return ranked


def select_primary_and_backup(
    ranked_candidates: List[ObjectiveCandidate],
) -> Tuple[ObjectiveCandidate, ObjectiveCandidate]:
    """
    Select primary (top-ranked) and backup (2nd-ranked) objectives.
    """
    if len(ranked_candidates) < 1:
        raise ValueError("No candidates available for selection")
    
    primary = ranked_candidates[0]
    
    # If only 1 candidate, use it as backup too
    backup = ranked_candidates[1] if len(ranked_candidates) > 1 else primary
    
    return primary, backup


# --- Plan Generation ---------------------------------------------------------------

def generate_plan(
    candidate: ObjectiveCandidate,
    is_primary: bool = True,
) -> DayPlan:
    """
    Generate a day plan for the candidate.
    
    Delegates to domain adapter for domain-specific details.
    """
    objective = candidate.objective
    adapter = get_adapter(objective.domain)
    
    # Adapter provides domain-specific plan details
    plan_details = adapter.generate_plan(
        objective,
        candidate.scores if candidate.scores else None,
        candidate.weather_days,
        is_primary=is_primary,
    )
    if candidate.location_metadata:
        plan_details.location_coordinates = candidate.location_coordinates or _extract_coordinates(
            candidate.location_metadata
        )
        if "bounds" in candidate.location_metadata:
            plan_details.area_bounds = candidate.location_metadata.get("bounds")
    if candidate.route_options:
        route_lines = []
        for route in candidate.route_options[:3]:
            parts = [route.name]
            if route.grade:
                parts.append(route.grade)
            if route.length_ft is not None:
                parts.append(f"{route.length_ft} ft")
            route_lines.append(" | ".join(parts))
        if route_lines:
            plan_details.routes_or_trails = route_lines
    
    return plan_details


# --- Recommendation Assembly ---------------------------------------------------------------

def assemble_recommendation(
    primary: ObjectiveCandidate,
    backup: ObjectiveCandidate,
    total_candidates: int = 2,
) -> PlannerRecommendation:
    """
    Assemble the final recommendation from selected objectives.
    """
    # Determine verdict based on primary's score
    primary_score = primary.overall_sendability_score
    if primary_score >= 75:
        verdict = "GO"
    elif primary_score >= 55:
        verdict = "CAUTION"
    else:
        verdict = "NO-GO"
    
    # Build conditions summary from primary
    conditions = _build_conditions_summary(primary)
    
    # Build scores summary
    scores_dict = _build_scores_dict(primary)
    
    # Generate plans
    primary_plan = generate_plan(primary, is_primary=True)
    backup_plan = generate_plan(backup, is_primary=False)
    map_points = _build_map_points(primary, backup, primary_plan, backup_plan)
    
    # Generate explanation
    explanation = _build_explanation(primary, verdict)
    
    # Build recommendation
    recommendation = PlannerRecommendation(
        sendability_verdict=verdict,
        overall_sendability_score=primary_score,
        primary_objective=primary,
        backup_objective=backup,
        conditions_summary=conditions,
        sendability_scores=scores_dict,
        risk_flags=primary.scores.risk_flags if primary.scores else [],
        short_explanation=explanation,
        detailed_explanation=explanation,  # TODO: call LLM for longer version
        primary_plan=primary_plan,
        backup_plan=backup_plan,
        map_points=map_points,
        debug_context={
            "candidates_evaluated": total_candidates,
            "primary_score": primary_score,
            "backup_score": backup.overall_sendability_score,
        },
    )
    
    return recommendation


def _build_conditions_summary(candidate: ObjectiveCandidate) -> Dict[str, Any]:
    """Build human-readable conditions summary from weather data."""
    from ..scoring.generic import c_to_f, mps_to_mph
    
    if not candidate.weather_days:
        return {"status": "No weather data"}
    
    # Get first day as representative
    first_day = candidate.weather_days[0]
    
    return {
        "location_name": candidate.location_name,
        "temperature_f": int(c_to_f(first_day.temp_max_c)),
        "temperature_low_f": int(c_to_f(first_day.temp_min_c)),
        "precipitation_probability": int(first_day.precip_probability * 100),
        "wind_mph": int(mps_to_mph(first_day.wind_speed_max_mps)),
        "rock_condition": _infer_rock_condition(first_day),
        "forecast_confidence": _infer_forecast_confidence(len(candidate.weather_days)),
    }


def _infer_rock_condition(day: WeatherDay) -> str:
    """Infer rock condition from weather."""
    precip_prob = day.precip_probability
    
    if precip_prob > 0.6:
        return "wet"
    elif precip_prob > 0.3:
        return "damp"
    else:
        return "dry"


def _infer_forecast_confidence(num_days: int) -> str:
    """Infer forecast confidence based on forecast window."""
    if num_days <= 3:
        return "high"
    elif num_days <= 7:
        return "medium"
    else:
        return "low"


def _build_scores_dict(candidate: ObjectiveCandidate) -> Dict[str, float]:
    """Extract scoring breakdown for display."""
    if not candidate.scores:
        return {}
    
    return {
        "access": candidate.scores.access_score,
        "weather": candidate.scores.weather_score,
        "crowd": candidate.scores.crowd_score,
        "risk": candidate.scores.risk_score,
        "overall": candidate.scores.trip_readiness_score,
    }


def _build_explanation(candidate: ObjectiveCandidate, verdict: str) -> str:
    """Build a short explanation of the verdict."""
    location = candidate.location_name
    score = candidate.overall_sendability_score
    
    if verdict == "GO":
        return f"Excellent window for {location}. Conditions favorable; plan accordingly."
    elif verdict == "CAUTION":
        return f"{location} is doable this weekend, but watch conditions. Plan for flexibility."
    else:
        return f"Not ideal for {location} right now. Consider waiting or backup location."


def _extract_coordinates(location_meta: Dict[str, Any]) -> Optional[Dict[str, float]]:
    """Normalize lat/lon metadata for UI and plan rendering."""
    lat = location_meta.get("lat")
    lon = location_meta.get("lon")
    if lat is None or lon is None:
        return None
    return {"lat": float(lat), "lon": float(lon)}


def _build_selection_reason(candidate: ObjectiveCandidate) -> str:
    """Build a concise recommendation rationale for UI display."""
    reasons: List[str] = []
    metadata = candidate.location_metadata or {}
    objective = candidate.objective

    if objective.domain == "climbing":
        rock_type = metadata.get("primary_rock_type")
        climb_types = metadata.get("primary_climb_types") or []
        grade_range = metadata.get("grade_range")
        if rock_type and climb_types:
            reasons.append(
                f"{rock_type.title()} climbing with {', '.join(climb_types)} options."
            )
        if grade_range:
            reasons.append(f"Known for a workable grade band of {grade_range}.")
        if candidate.scores:
            if candidate.scores.weather_score >= 75:
                reasons.append("Forecast looks favorable for a productive climbing window.")
            elif candidate.scores.weather_score >= 60:
                reasons.append("Conditions look workable if you stay flexible on timing.")
            else:
                reasons.append("Weather is the main limiter, so treat this as a backup-quality option.")
        if candidate.route_options:
            top_routes = [
                f"{route.name} ({route.grade})" if route.grade else route.name
                for route in candidate.route_options[:2]
            ]
            reasons.append(f"Representative route options include {', '.join(top_routes)}.")
    else:
        reasons.append(candidate.match_reason or "Matches the requested planning constraints.")
        if candidate.scores and candidate.scores.weather_score >= 70:
            reasons.append("Forecast is aligned with the trip window.")

    return " ".join(reasons).strip() or "Selected because it best matches the current window."


def _build_map_points(
    primary: ObjectiveCandidate,
    backup: ObjectiveCandidate,
    primary_plan: DayPlan,
    backup_plan: DayPlan,
) -> List[MapPoint]:
    """Create a compact set of UI-ready map markers."""
    map_points: List[MapPoint] = []
    seen: set[tuple[str, float, float, str]] = set()

    point_specs = [
        (primary, primary_plan, "primary"),
        (backup, backup_plan, "backup"),
    ]

    for candidate, plan, role in point_specs:
        coords = plan.location_coordinates or candidate.location_coordinates
        if not coords:
            continue

        lat = coords.get("lat")
        lon = coords.get("lon")
        if lat is None or lon is None:
            continue

        dedupe_key = (candidate.candidate_id, float(lat), float(lon), role)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        map_points.append(
            MapPoint(
                point_id=f"{candidate.candidate_id}_{role}",
                label=candidate.location_name,
                lat=float(lat),
                lon=float(lon),
                point_type="objective",
                role=role,
                score=candidate.overall_sendability_score,
                description=candidate.selection_reason or candidate.match_reason,
            )
        )

    return map_points


# --- Main Orchestrator ---------------------------------------------------------------

def plan_outdoor_objective(request: RecommendationRequest) -> PlannerRecommendation:
    """
    Main entry point: plan an outdoor objective end-to-end.
    
    Orchestrates: generate → evaluate → rank → select → assemble.
    
    Args:
        request: User request with domain, dates, constraints
    
    Returns:
        PlannerRecommendation with verdict, objectives, plans, explanation
    """
    logger.info(f"Planning {request.domain} objective for {request.start_date} to {request.end_date}")
    
    # 1. Generate candidates
    candidates = generate_candidates(request)
    logger.info(f"Generated {len(candidates)} candidates")
    
    if not candidates:
        raise ValueError(f"No candidates found for {request.domain}")
    
    # 2. Evaluate candidates
    evaluated = evaluate_candidates(candidates)
    logger.info(f"Evaluated {len(evaluated)} candidates")
    
    # 3. Rank
    ranked = rank_candidates(evaluated)
    
    # 4. Select primary and backup
    primary, backup = select_primary_and_backup(ranked)
    
    # 5. Assemble recommendation
    recommendation = assemble_recommendation(primary, backup, total_candidates=len(ranked))
    
    logger.info(f"Recommendation: {recommendation.sendability_verdict} ({recommendation.overall_sendability_score})")
    
    return recommendation


__all__ = [
    "generate_candidates",
    "evaluate_candidates",
    "rank_candidates",
    "select_primary_and_backup",
    "generate_plan",
    "assemble_recommendation",
    "plan_outdoor_objective",
]
