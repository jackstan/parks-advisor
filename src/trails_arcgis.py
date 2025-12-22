from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import time
import math
import requests
import heapq


ARCGIS_TRAILS_QUERY_URL = (
    "https://mapservices.nps.gov/arcgis/rest/services/"
    "NationalDatasets/NPS_Public_Trails/FeatureServer/0/query"
)

_CACHE: Dict[str, Tuple[float, List["TrailCard"]]] = {}
_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours


# ----------------------------- Data model ------------------------------------

@dataclass(frozen=True)
class TrailCard:
    name: str
    unit_code: str
    source: str

    route_class: str  # loop | out_and_back | network | unknown

    one_way_miles: Optional[float] = None
    loop_miles: Optional[float] = None
    span_miles: Optional[float] = None
    total_miles: Optional[float] = None
    notes: Optional[str] = None


# ----------------------------- Geometry utils --------------------------------

EARTH_RADIUS_M = 6371000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _polyline_length_m(paths: List[List[List[float]]]) -> float:
    total = 0.0
    for path in paths or []:
        for i in range(1, len(path)):
            lon1, lat1 = path[i - 1]
            lon2, lat2 = path[i]
            total += _haversine_m(lat1, lon1, lat2, lon2)
    return total


def _mean_lat_lon(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    lat = sum(p[0] for p in points) / len(points)
    lon = sum(p[1] for p in points) / len(points)
    return lat, lon


# ----------------------------- ArcGIS fetch ----------------------------------

def _fetch_arcgis_features_for_unit(unit_code: str) -> List[dict]:
    params = {
        "where": f"UNITCODE='{unit_code.upper()}'",
        "outFields": "TRLNAME,UNITCODE,NOTES",
        "returnGeometry": "true",
        "outSR": 4326,
        "geometryPrecision": 6,
        "f": "json",
        "resultOffset": 0,
        "resultRecordCount": 2000,
    }

    out = []
    offset = 0
    while True:
        params["resultOffset"] = offset
        r = requests.get(ARCGIS_TRAILS_QUERY_URL, params=params, timeout=45)
        r.raise_for_status()
        data = r.json()
        feats = data.get("features") or []
        if not feats:
            break
        out.extend(feats)
        offset += len(feats)
        if len(feats) < params["resultRecordCount"]:
            break
    return out


# ----------------------------- Graph helpers ---------------------------------

def _latlon_to_local_xy_m(lat, lon, lat0, lon0):
    x = (math.radians(lon - lon0) * math.cos(math.radians(lat0))) * EARTH_RADIUS_M
    y = math.radians(lat - lat0) * EARTH_RADIUS_M
    return x, y


def _snap_nodes(endpoints, snap_m=25.0):
    lat0, lon0 = _mean_lat_lon(endpoints)
    grid, nodes, ids = {}, [], []

    def cell(lat, lon):
        x, y = _latlon_to_local_xy_m(lat, lon, lat0, lon0)
        return int(x // snap_m), int(y // snap_m)

    for lat, lon in endpoints:
        ck = cell(lat, lon)
        found = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for nid in grid.get((ck[0] + dx, ck[1] + dy), []):
                    if _haversine_m(lat, lon, *nodes[nid]) <= snap_m:
                        found = nid
                        break
        if found is None:
            found = len(nodes)
            nodes.append((lat, lon))
            grid.setdefault(ck, []).append(found)
        ids.append(found)

    return nodes, ids


def _component_diameter(adj, nodes):
    def dijkstra(src):
        dist = {src: 0.0}
        pq = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d != dist[u]:
                continue
            for v, w in adj.get(u, []):
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        far = max(nodes, key=lambda n: dist.get(n, 0.0))
        return dist, far

    _, a = dijkstra(nodes[0])
    dist, b = dijkstra(a)
    return dist.get(b, 0.0)


def _loop_core_length(nodes, edges):
    deg = {n: 0 for n in nodes}
    adj = {n: [] for n in nodes}
    for u, v, w in edges:
        deg[u] += 1
        deg[v] += 1
        adj[u].append((v, w))
        adj[v].append((u, w))

    stack = [n for n, d in deg.items() if d <= 1]
    keep = {n: True for n in nodes}

    while stack:
        n = stack.pop()
        if not keep[n]:
            continue
        keep[n] = False
        for nb, _ in adj[n]:
            if keep[nb]:
                deg[nb] -= 1
                if deg[nb] == 1:
                    stack.append(nb)

    core = {n for n, k in keep.items() if k}
    return sum(w for u, v, w in edges if u in core and v in core)


# ----------------------------- Build TrailCard --------------------------------

def _build_trail_card(name, unit, notes, segments):
    endpoints = []
    for s in segments:
        endpoints += s["endpoints"]

    nodes, ids = _snap_nodes(endpoints)
    edges = []

    for i, s in enumerate(segments):
        a, b = ids[2 * i], ids[2 * i + 1]
        if a != b:
            edges.append((a, b, s["length_m"]))

    if not edges:
        return TrailCard(name, unit, "nps_arcgis", "unknown", notes=notes)

    adj = {}
    for u, v, w in edges:
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))

    visited, comps = set(), []
    for n in adj:
        if n in visited:
            continue
        stack, comp_nodes = [n], []
        visited.add(n)
        while stack:
            x = stack.pop()
            comp_nodes.append(x)
            for y, _ in adj[x]:
                if y not in visited:
                    visited.add(y)
                    stack.append(y)
        comp_edges = [(u, v, w) for u, v, w in edges if u in comp_nodes and v in comp_nodes]
        comps.append((comp_nodes, comp_edges))

    main_nodes, main_edges = max(comps, key=lambda c: sum(w for _, _, w in c[1]))
    total_m = sum(w for _, _, w in main_edges)

    deg = {n: 0 for n in main_nodes}
    for u, v, _ in main_edges:
        deg[u] += 1
        deg[v] += 1

    endpoints_nodes = [n for n, d in deg.items() if d == 1]
    max_deg = max(deg.values())

    route_class = "unknown"
    if len(endpoints_nodes) == 0 and max_deg == 2:
        route_class = "loop"
    elif len(endpoints_nodes) == 2 and max_deg <= 2:
        a, b = endpoints_nodes
        gap = _haversine_m(*nodes[a], *nodes[b])
        route_class = "loop" if gap <= 75 else "out_and_back"
    elif max_deg > 2 or len(endpoints_nodes) > 2:
        route_class = "network"

    one_way = loop = span = None
    main_adj = {}
    for u, v, w in main_edges:
        main_adj.setdefault(u, []).append((v, w))
        main_adj.setdefault(v, []).append((u, w))

    if route_class == "loop":
        loop = _loop_core_length(main_nodes, main_edges)
    elif route_class == "out_and_back":
        one_way = _component_diameter(main_adj, main_nodes)
    elif route_class == "network":
        span = _component_diameter(main_adj, main_nodes)

    def m_to_mi(x):
        return round(x / 1609.344, 2) if x else None

    card = TrailCard(
        name=name,
        unit_code=unit,
        source="nps_arcgis",
        route_class=route_class,
        one_way_miles=m_to_mi(one_way),
        loop_miles=m_to_mi(loop),
        span_miles=m_to_mi(span),
        total_miles=m_to_mi(total_m),
        notes=notes,
    )

    # ---------------- DEBUG OUTPUT ----------------
    lname = name.lower()
    if "mirror lake" in lname or "wawona meadow" in lname:
        print("[DEBUG TRAIL]", card)

    return card


# ----------------------------- Public API ------------------------------------

def get_trail_cards_for_unit_code(unit_code: str) -> List[TrailCard]:
    unit_code = unit_code.upper()
    now = time.time()

    cached = _CACHE.get(unit_code)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    feats = _fetch_arcgis_features_for_unit(unit_code)
    grouped: Dict[str, Dict[str, Any]] = {}

    for f in feats:
        a = f.get("attributes") or {}
        g = f.get("geometry") or {}
        name = (a.get("TRLNAME") or "").strip()
        if not name:
            continue

        paths = g.get("paths") or []
        if not paths:
            continue

        p = max(paths, key=len)
        if len(p) < 2:
            continue

        lon1, lat1 = p[0]
        lon2, lat2 = p[-1]
        length_m = _polyline_length_m(paths)

        key = name.lower()
        grouped.setdefault(key, {
            "name": name,
            "unit": a.get("UNITCODE") or unit_code,
            "notes": a.get("NOTES"),
            "segments": [],
        })["segments"].append({
            "endpoints": ((lat1, lon1), (lat2, lon2)),
            "length_m": length_m,
        })

    cards = [
        _build_trail_card(
            g["name"],
            g["unit"],
            g["notes"],
            g["segments"],
        )
        for g in grouped.values()
    ]

    cards.sort(key=lambda c: c.name.lower())
    _CACHE[unit_code] = (now, cards)
    return cards
