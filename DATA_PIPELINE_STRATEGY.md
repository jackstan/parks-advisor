# Data Pipeline Strategy

## Summary

Sendable should use a **shared planning core with domain-owned data pipelines**.

That means:
- `climbing`, `hiking`, `skiing`, and future domains each own their own source adapters, normalization logic, and domain-specific metadata.
- Shared services such as weather, geospatial utilities, planner orchestration, recommendation models, and map output contracts stay common.
- We should **not** force climbing routes, ski lines, hiking trails, park units, and guidebook content into one generic ingestion schema too early.

The current codebase is close to this shape conceptually, but it was still mixing domain catalogs and provider selection into shared orchestration. A small improvement has now been made:
- domain adapters explicitly own their location catalogs
- domain adapters now expose alert/content provider hooks
- planner/orchestration uses those adapter hooks instead of hard-coding park-specific source choices

## Shared vs Domain-Specific Responsibilities

### Shared responsibilities

These should remain common across all domains:
- planner request/response interfaces such as `RecommendationRequest`, `ObjectiveCandidate`, `PlannerRecommendation`
- weather retrieval by coordinates
- geospatial helpers and map rendering contracts
- generic recommendation assembly and ranking flow
- shared map-ready output fields such as objective coordinates, map points, optional route geometry
- caching primitives and common provenance conventions

Shared code should answer:
- how the planner evaluates candidates
- how map-ready results are returned
- how weather is fetched for a lat/lon window
- how the UI consumes recommendations

Shared code should **not** decide:
- which domain source is authoritative
- how a climbing crag differs from a ski zone or hiking trail
- which metadata fields are required for domain scoring beyond the shared minimum

### Domain-specific responsibilities

Each domain should own:
- source adapters for its own APIs, files, scraped sources, or curated catalogs
- normalization into domain-native records
- domain-specific objective/location metadata
- domain scoring inputs and heuristics
- domain content enrichment and RAG source selection
- domain alert interpretation

Examples:
- climbing: crags, route areas, condition reports, guide sources, drying time, rock type, grade range
- hiking: trailheads, trails, park alerts, closures, permit zones, difficulty/duration
- skiing: zones, lift-access vs touring, avalanche products, aspect/elevation bands, snowpack and wind loading

## Recommended Storage Boundaries

Use storage boundaries that keep raw source differences intact.

### 1. Raw source cache

Store source-native payloads separately by domain and provider.

Examples:
- `climbing/openbeta/...`
- `climbing/conditions_reports/...`
- `hiking/nps/...`
- `skiing/avalanche_center/...`

Rules:
- immutable or append-only where practical
- keep source ids, fetch timestamps, and raw payloads
- never coerce all raw sources into one global schema

### 2. Domain-normalized datasets

Each domain should maintain its own normalized records derived from raw sources.

Examples:
- climbing normalized area catalog
- climbing normalized route summaries
- hiking normalized trail catalog
- skiing normalized zone/run metadata

Rules:
- normalize only within the domain
- keep domain-specific fields first-class
- include shared map metadata and provenance fields
- avoid forcing skiing/climbing/hiking into a single `route` table

### 3. Shared operational caches

Shared caches should exist only for truly common services:
- weather responses by coordinate/date window
- geospatial reverse lookups or tiling helpers
- map geometry simplification or viewport helpers

These caches are common because they do not define the domain object model.

### 4. Planner-ready recommendation outputs

Planner outputs should remain shared and map-ready:
- selected objective ids
- summary scores
- conditions summary
- risk flags
- map points
- optional route/approach geometry

This is the layer the UI should consume.

## Recommended Runtime Pipeline Shape

For each domain, the pipeline should look like:

1. Domain adapter selects the location catalog and source providers.
2. Domain source adapters fetch raw domain data.
3. Domain normalization produces domain-native records with shared map metadata.
4. Shared services add cross-domain signals such as weather.
5. Domain adapter computes domain-specific scores and plan details.
6. Shared planner assembles ranked, map-ready recommendations.

This keeps the planner generic without making the data model generic too early.

## Example Climbing Structure

Recommended direction for climbing-specific code:

```text
src/
  domains/
    climbing/
      models.py
      catalog.py
      pipeline.py
      sources/
        openbeta.py
        mountain_project.py
        condition_reports.py
      normalize.py
      scoring.py
```

The current repo does not need a full move yet. For now, the important boundary is:
- shared orchestration calls the climbing adapter
- the climbing adapter owns the climbing catalog and source-provider choices
- climbing metadata remains climbing-shaped

### Example climbing data model

```python
ClimbingAreaRecord(
    area_id="rrg",
    name="Red River Gorge",
    map={
        "lat": 38.5,
        "lon": -83.7,
        "bounds": None,
    },
    rock_type="sandstone",
    climb_types=["sport", "trad"],
    grade_band="5.6-5.12c",
    approach_profile="moderate",
    drying_time_hours=24,
    seasonality=["spring", "fall"],
    source_refs=["seed_catalog_v1"],
)
```

### Example climbing adapter responsibilities

- return the climbing location catalog
- choose climbing-specific alert providers, if any
- choose climbing-specific content providers
- interpret weather into rock-condition and sendability signals
- generate climbing-specific itinerary fields

## Map Metadata Requirements

Every objective/location record that can be shown on the map should include these required fields:
- stable `location_id`
- display `name`
- `domain`
- `location_type`
- `lat`
- `lon`
- `timezone`
- source provenance (`source_name` or equivalent)

Recommended optional fields:
- `bounds` for areas or regions
- `route_coordinates` for linestring geometry
- `approach_coordinates` if approach display matters
- `elevation`
- `viewport_hint` or preferred zoom
- human-readable location summary for tooltips

Rules for map data:
- coordinates should be WGS84 lat/lon
- point coordinates are required even when richer geometry exists
- geometry should be optional and domain-specific
- map metadata should travel with the normalized domain record, not be invented later in the UI

## What Should Stay Flexible for Skiing

Skiing should not be forced into climbing-style fields.

Keep these flexible:
- objective type: resort run, touring objective, ski mountaineering line, zone
- hazard inputs: avalanche bulletin, wind slab, aspect, elevation band, freeze/thaw, snowfall timing
- geometry shape: point, polygon, descent line, access corridor
- access model: lift-access, trailhead, road gate, skin track
- scoring dimensions: snow quality, avalanche hazard, visibility, wind loading, access, timing
- content sources: avalanche centers, resort reports, mountain weather, user observations

Do not require skiing to fit:
- climbing grade ranges
- rock-condition heuristics
- crag-style area metadata
- park-specific alert assumptions

## Conservative Improvements Made Now

Implemented in the current codebase:
- domain adapters now expose `get_location_catalog()`
- domain adapters now expose `get_alert_provider()` and `get_content_providers()`
- planner candidate generation now reads from the adapter-owned domain catalog
- planner/orchestration alert selection now goes through the domain adapter instead of assuming NPS/parks

Why this helps:
- it makes domain data ownership explicit now
- it reduces park-specific leakage into shared orchestration
- it gives skiing a clean place to attach future source adapters without a large rewrite

## Near-Term Next Steps

Recommended next incremental changes, without a major refactor:
- split `src/adapters/__init__.py` into per-domain modules once the next domain is added
- introduce domain-specific normalized record types under `src/domains/<domain>/models.py`
- add provenance fields consistently to normalized location/objective records
- move curated catalogs out of `config.py` into domain-owned catalog modules when they grow beyond seed data

This keeps Sendable extensible across domains while preserving the fact that each outdoor domain has different source systems, schemas, and planning logic.
