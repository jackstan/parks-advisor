# Climbing Search Flow

## Summary

The climbing retrieval flow now distinguishes between two user intents:
- **destination search** for a climbing destination such as `Smith Rock`, `Yosemite National Park`, or `Red Rock`
- **origin search** for a city or starting point such as `San Francisco`, `Oakland`, or `Sacramento`

This change improves the existing OpenBeta integration without changing the overall planner architecture.
It also adds a local climbing area index that sits in front of OpenBeta and translates fuzzy user place input into stronger search targets or practical geographic anchors.

## Local Translation Layer

Before Sendable talks to OpenBeta, it now checks a local climbing area index.

That layer is used to:

1. normalize fuzzy place input
2. match it against known higher-level climbing regions or clusters
3. generate stronger OpenBeta search targets
4. provide a practical origin anchor for phrases that are more regional than literal

Examples:

- `Yosemite National Park` maps to a Yosemite cluster and expands into better search targets such as `Yosemite Valley`
- `north of San Francisco` maps to the `North Bay / Marin` cluster and uses that cluster centroid as the starting geography
- `San Francisco` geocodes live, but the nearby Bay Area clusters are still used as local context

## Destination Search

Destination search works like this:

1. Search OpenBeta by area name.
2. Also search OpenBeta by path tokens for destination-style names such as parks or regions.
3. Select the most relevant destination area.
4. Expand that destination into child crags or sub-areas where available.
5. Fetch route-level data for those smaller sub-areas.
6. Build planner candidates from the route-bearing crags rather than only from the parent destination.

Why this is better:
- the planner gets actual climbing options
- route names and grades are available for cards/plan summaries
- map pins still work from the area/crag coordinates

## Origin Search

Origin search works like this:

1. Geocode the free-form input using Nominatim.
2. Check the local area index for nearby climbing clusters or regional intent.
3. If the result looks like a city/town/origin rather than a climbing destination, treat it as origin search.
4. Use OpenBeta `cragsNear` with the geocoded point or a local cluster centroid.
5. Compute practical distance from the origin.
6. Fetch route-level data for the nearby crags.
7. If live nearby retrieval is thin, use the local cluster targets to seed fallback destination searches.
8. Rank nearby climbing options by distance first, then climbing density.

This allows queries like `San Francisco` to surface actual nearby climbing rather than trying to match a literal area name.

## Route-Level Data Source

Route-level data comes from OpenBeta `area(uuid) { climbs { ... } }`.

Currently used route metadata:
- route name
- route grade
- route length when available
- route type flags
- route safety
- route coordinates when available
- route ordering metadata (`left_right_index`)
- Mountain Project route id when available through OpenBeta metadata

This route data is normalized into internal `RouteOption` records before being attached to planner candidates.

## Current Limitations

- OpenBeta route expansion can be slow or flaky for some larger areas.
- Parent mega-destination queries are intentionally avoided; the system fetches routes from smaller child crags instead.
- Some OpenBeta areas return incomplete coordinates or no route length.
- Nearby search currently uses a fixed practical radius and simple ranking rather than a learned ranking model.
- The planner still scores at the crag/area level; route enrichment currently improves retrieval and display, not per-route scoring.

## Implementation Notes

Relevant modules:
- `src/integrations/climbing/area_index.py`
- `src/integrations/climbing/data/area_index.json`
- `src/integrations/climbing/openbeta_client.py`
- `src/integrations/geocoding/nominatim_client.py`
- `src/orchestration/planner.py`

The planner and UI architecture remain unchanged:
- free-form input still becomes a `RecommendationRequest`
- candidates still flow through existing weather/scoring/ranking
- primary and backup recommendations still return map-ready coordinates
