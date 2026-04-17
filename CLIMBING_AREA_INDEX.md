# Climbing Area Index

## What Is Stored Locally

Sendable now keeps a small local climbing area index in:

- `src/integrations/climbing/data/area_index.json`

This is not a replacement for OpenBeta. It is a lightweight translation layer that stores higher-level climbing regions and clusters with stable metadata that is useful for search, map UX, and query interpretation.

Current fields per entry:

- `entry_id`
- `uuid`
- `area_name`
- `parent_uuid`
- `path`
- `lat`
- `lng`
- `region`
- `state`
- `country`
- `aliases`
- `search_targets`
- `cluster_type`
- `serves_origins`

Notes:

- `uuid` and `parent_uuid` are optional because the local layer is allowed to carry partial records before a live OpenBeta lookup completes.
- `lat` and `lng` represent a practical cluster centroid, not necessarily a specific crag pin.
- `search_targets` are the stronger destination terms that Sendable should prefer when it talks to OpenBeta.

## How The Translation Layer Works

The resolver lives in:

- `src/integrations/climbing/area_index.py`

The resolution flow is intentionally simple:

1. Normalize the free-form user text.
2. Strip common low-signal words such as `climb`, `near`, and `want`.
3. Score local area index entries against the query using:
   - area name
   - aliases
   - search targets
   - path/hierarchy tokens
   - served origin names
4. Return:
   - matched higher-level climbing clusters
   - stronger destination search targets
   - nearby clusters for geocoded origins
   - an optional origin anchor for region-like phrases

Examples:

- `Yosemite National Park` resolves to the Yosemite cluster and then produces stronger OpenBeta search targets such as `Yosemite Valley` and `Tuolumne Meadows`.
- `north of San Francisco` resolves to the `North Bay / Marin` cluster and uses that centroid as a geographic anchor instead of sending the raw sentence to OpenBeta.
- `San Francisco` still geocodes live, but the local index contributes nearby Bay Area cluster context such as North Bay, East Bay, and South Bay.

## What Remains Live From OpenBeta

The local index does not attempt to mirror climbing content.

These pieces still come live from OpenBeta:

- destination area lookup
- path-token area lookup
- nearby crag lookup
- route-level enrichment
- route metadata such as grades, length, and type

That means the local layer improves interpretation, while OpenBeta remains the source of truth for climbing inventory and route details.

## Current Scope

This index is intentionally small and climbing-first.

It currently focuses on:

- high-signal national destinations
- Bay Area regional clusters
- a few western and eastern U.S. climbing hubs

That keeps the system practical for v1 and compatible with future map/search UX, where these same indexed entries can back autocomplete, region chips, and map overlays.
