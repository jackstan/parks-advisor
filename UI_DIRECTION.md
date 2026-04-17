# UI Direction

## v1 Stack Decision

Keep the current `Streamlit` stack for v1.

Why:
- The current product need is a faster decision/planning surface, not a broad frontend platform rewrite.
- `Streamlit` is sufficient for the next demoable iteration: form input, structured recommendation output, and a practical map using built-in `pydeck`.
- Rewiring the existing app to the planner API is materially cheaper and lower-risk than a full migration right now.

This means the v1 UI should remain incremental:
- Replace the old parks-advisor framing with a Sendable planning workflow.
- Center the UI on sendability, primary/backup objectives, reasoning, conditions, risks, itinerary, and map.
- Keep the planner schema structured so a future frontend can consume the same response cleanly.

## Recommended Future Stack

For the first major post-v1 frontend upgrade, move to:
- `Next.js` + `React`
- `TypeScript`
- `MapLibre GL JS` or `deck.gl` for map rendering

Why this is the better long-term stack:
- The product wants a richer planning workflow than a simple form/result loop.
- Maps will become central product UI, not just supporting visualization.
- A typed React app will handle richer state, saved plans, comparisons, collaborative editing, and map interactions more cleanly than Streamlit.
- `MapLibre` or `deck.gl` is a better fit for route geometry, weather overlays, clustering, and interactive objective layers.

This migration is not clearly necessary for the current stage because:
- The planner/domain model is still evolving.
- The immediate goal is a credible climbing-first v1 demo.
- The current Streamlit app can still express the key product decisions without blocking backend progress.

## Map Evolution

### v1

Use the current lightweight map to reinforce the recommendation:
- Show the primary and backup objective locations.
- Differentiate them visually by color and tooltip copy.
- Keep the map adjacent to the objective decision output so it feels functional, not decorative.

### Later Versions

The map should evolve from point markers into a planning workspace:
- Draw objective approach lines and route geometry when coordinates are available.
- Add objective filters by domain, style, grade band, and sendability score.
- Layer in weather context such as precip/wind overlays and forecast changes by hour.
- Support comparing multiple objectives on the same map with selection state tied to the plan panel.
- Add saved plans, recents, and collaborative sharing around map state.

### Architecture Guidance

Keep the backend recommendation schema map-ready now:
- objective coordinates
- optional route coordinates
- UI-ready map markers for primary and backup objectives

That keeps the current Streamlit UI simple while avoiding a schema rewrite when a richer frontend arrives.
