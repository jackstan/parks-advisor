# Architecture Migration: Park-Centric → Objective-Centric

**Date**: April 2026  
**Status**: In Progress (Phase 1 complete)  
**Summary**: Refactored codebase from parks/NPS-specific architecture to domain-agnostic objective-oriented design.

---

## What Changed

### New Directory Structure

```
src/
├── domain/                        [NEW] Domain layer
│   ├── __init__.py
│   └── objective_models.py        Generic objective models
├── orchestration/                 [NEW] Orchestration layer
│   ├── __init__.py                Main orchestrator functions
│   └── planner.py                 (placeholder for future expansion)
├── integrations/                  [NEW] External integrations (pluggable)
│   ├── weather/
│   │   └── __init__.py            Open-Meteo client (domain-agnostic)
│   ├── alerts/
│   │   ├── __init__.py            Alert provider interface
│   │   └── nps.py                 NPS alert provider
│   └── content/
│       └── __init__.py            Content provider interface + NPS wrapper
├── scoring/                       [NEW] Scoring layer (extracted)
│   ├── __init__.py
│   ├── generic.py                 Domain-agnostic utilities
│   └── hiking.py                  (placeholder for hiking-specific logic)
├── adapters/                      [NEW] Domain adapters (pluggable)
│   └── __init__.py                ObjectiveAdapter base + HikingAdapter + ClimbingAdapter (stub)
├── models.py                      [EXISTING] Extended with deprecation notes
├── config.py                      [REFACTORED] Added CLIMBING_AREAS + factory functions
├── advisor_llm.py                 [EXISTING] No changes (generic)
├── advisor.py                     [EXISTING] No changes
├── scoring.py                     [EXISTING] Entry point remains; logic moved to src/scoring/
├── advisor_context.py             [EXISTING] Will be refactored in Phase 2
└── ... (other files unchanged)
```

### Backward Compatibility

**Preserved (no breaking changes)**:
- `TripRequest` dataclass still exists in `models.py` (marked @deprecated)
- `PARKS` config dict still available
- `src/weather_client.py` still works (calls through integrations now)
- `app.py` and `ui_streamlit.py` workflows unchanged
- `src/scoring.py` entry point still exists (internal reorganization)

**Aliased for clarity**:
- `ObjectiveRequest = Objective` (in `domain/objective_models.py`)
- `get_weather_for_trip()` → calls `get_weather_for_location()` internally

**Added (non-breaking)**:
- `src/domain/objective_models.py` – new base models
- `src/orchestration/` – new orchestration layer
- `src/integrations/` – new integration abstractions
- `src/adapters/` – new domain adapter pattern
- `src/scoring/` – reorganized scoring logic
- Factory functions: `get_objective_location()`, `get_locations_by_domain()` in config

---

## Key Architectural Improvements

### 1. Domain Adapters (Pluggable)

**Before**: Hiking logic mixed into core modules. To add climbing, you'd fork scoring, prompting, context building.

**After**: Each domain (hiking, climbing, skiing) has an `ObjectiveAdapter` implementing:
- `compute_scores()` – domain-specific scoring
- `format_context_for_llm()` – domain-specific context
- `get_system_message()` – domain-specific LLM guidance
- `parse_verdict()` – domain-specific verdict logic

Adding a new domain = write 1 adapter class (~100 lines), no changes to core.

### 2. Integrations Layer (Pluggable)

**Before**: NPS client calls scattered; Open-Meteo wired directly to parks; hard to swap implementations.

**After**: Clean interfaces:
- `AlertProvider` (abstract) → `NPSAlertProvider` (concrete) → climbing providers later
- `ContentProvider` (abstract) → `NPSContentProvider` (concrete) → climbing guides later
- `get_weather_for_location()` (generic) → works for any lat/lon, any domain

### 3. Objective Model (Extensible)

**Before**: `TripRequest` with park_code, hiker_profile, activity_type. Hard to add route grades, exposure levels, etc.

**After**: 
- Base `Objective` with location_id, domain, constraints
- Subclasses (`HikingObjective`, `ClimbingObjective`) add domain-specific fields
- Easy to extend for skiing (new subclass) without touching core

### 4. Scoring Modularization

**Before**: `src/scoring.py` = hiking-specific weights, thresholds, conversions all mixed.

**After**:
- `src/scoring/generic.py` – unit conversions, common thresholds (reusable)
- `src/scoring/hiking.py` – hiking-specific logic (placeholder; can grow)
- `src/scoring/climbing.py` – climbing-specific logic (stub for v1.1)
- Old `src/scoring.py` becomes a dispatcher/entry point

---

## Migration Guide for Developers

### Using the New Objective API

**Old way** (still works):
```python
from src.models import TripRequest
from src.advisor_context import build_trip_context
from src.advisor_llm import advise_trip_with_explanation

trip = TripRequest(park_code="yose", ...)
context = build_trip_context(trip)
scores, explanation = advise_trip_with_explanation(trip)
```

**New way** (recommended for new features):
```python
from src.domain.objective_models import Objective, UserConstraints
from src.orchestration import evaluate_objective
from src.config import get_objective_location

objective = Objective(
    objective_id="clim_001",
    location_id="rrg",
    location_type="climbing_area",
    domain="climbing",
    start_date="2026-04-20",
    end_date="2026-04-22",
    constraints=UserConstraints(
        max_duration_hours=8,
        max_approach_minutes=120,
        skill_level="advanced",
    ),
)

location_metadata = get_objective_location("climbing", "rrg")
recommendation = evaluate_objective(objective, location_metadata)

print(recommendation.verdict)  # "GO", "CAUTION", or "NO-GO"
print(recommendation.short_explanation)
```

### Adding a New Domain (e.g., Skiing)

1. **Define domain models** (optional, if extending `Objective`):
   ```python
   # src/domain/skiing_objective.py
   @dataclass
   class SkiingObjective(Objective):
       aspect: str  # "N", "NE", "E", etc.
       elevation_gain_ft: int
       avalanche_danger_level: str  # from USAC
   ```

2. **Create a domain adapter**:
   ```python
   # src/adapters/__init__.py (add to existing file)
   class SkiingAdapter(ObjectiveAdapter):
       def compute_scores(self, objective, weather_days, context) -> Scores:
           # skiing-specific scoring
           pass
       # ... other methods
   
   # Update factory:
   def get_adapter(domain: str) -> ObjectiveAdapter:
       if domain == "skiing":
           return SkiingAdapter()
       ...
   ```

3. **Add location data** (if applicable):
   ```python
   # src/config.py
   SKI_ZONES = {
       "tahoe_backcountry": {...},
       ...
   }
   
   # Update factory functions:
   def get_objective_location(domain: str, location_id: str):
       if domain == "skiing":
           return SKI_ZONES[location_id]
       ...
   ```

4. **Optionally create domain-specific integrations**:
   ```python
   # src/integrations/avalanche/
   # src/integrations/hut_availability/
   # etc.
   ```

That's it. The core orchestrator (`evaluate_objective()`) works automatically.

---

## What's Still the Same

### Reused Modules (No Changes Needed)

- **`src/embeddings/`** – local embedding infrastructure (domain-agnostic)
- **`src/rag/`** – vector DB + retrieval (domain-agnostic)
- **`src/weather_client.py`** – entry point still works (now wraps integrations)
- **`src/advisor_llm.py`** – LLM orchestration (domain-agnostic)
- **`src/nps_client.py`** – alerts client (wrapped in integrations layer)
- **`src/nps_articles.py`** – content client (wrapped in integrations layer)
- **UI entry points** – `app.py`, `ui_streamlit.py` still work

### Still Park-Centric (By Design, for Now)

These remain NPS/hiking-focused because hiking is still the primary use case for v1:
- `src/advisor_context.py` – hiking-specific RAG queries (will refactor in Phase 2)
- `src/prompt_builder.py` – hiking-specific prompts (will refactor in Phase 2)
- `src/nps_things_to_do.py` – hiking-focused (not yet integrated)
- `src/trails_arcgis.py` – hiking trails (not generalized yet)

These will be refactored when climbing becomes primary or multi-domain support is needed.

---

## Deprecation Path

### Phase 1 (Current): Foundation
- [x] Create domain/objective_models.py
- [x] Create orchestration/ layer
- [x] Create integrations/ abstractions
- [x] Create adapters/ pattern
- [x] Add CLIMBING_AREAS to config
- [x] Preserve backward compatibility

### Phase 2 (Soon): Refactor Context & Prompts
- [ ] Refactor `advisor_context.py` → `orchestration/objective_context.py`
- [ ] Make context building domain-aware (via adapters)
- [ ] Refactor `prompt_builder.py` for climbing
- [ ] Remove hiking-specific RAG queries

### Phase 3 (Later): Full Migration
- [ ] Mark `TripRequest` as @deprecated
- [ ] Migrate `app.py`, `ui_streamlit.py` to new API
- [ ] Remove aliases; require explicit imports
- [ ] Consolidate scoring logic fully into `src/scoring/`

---

## Testing the New Architecture

### Test Backward Compat (Hiking)
```bash
python app.py  # Should still work
streamlit run ui_streamlit.py  # Should still work
```

### Test New Objective API
```python
from src.domain.objective_models import Objective
from src.orchestration import evaluate_objective
from src.adapters import get_adapter

# Create a hiking objective the new way
hiking_obj = Objective(...)
adapter = get_adapter("hiking")
# Verify adapter is HikingAdapter and works

# Create a climbing objective the new way (will be climbing adapter)
climbing_obj = Objective(..., domain="climbing")
adapter = get_adapter("climbing")
# Verify adapter is ClimbingAdapter (even if stub)
```

---

## File Migration Summary

| File | Old Role | New Role | Status |
|------|----------|----------|--------|
| `src/models.py` | Core models | Extended with deprecation notes | Refactored |
| `src/config.py` | PARKS dict only | PARKS + CLIMBING_AREAS + factories | Refactored |
| `src/advisor_context.py` | Hiking context builder | Still used by hiking; will migrate to orchestration | Unchanged |
| `src/advisor_llm.py` | Hiking LLM orchestration | Generic LLM orchestration | Unchanged |
| `src/scoring.py` | Hiking scoring entry point | Dispatcher; logic moved to src/scoring/ | Refactored |
| `src/weather_client.py` | Park-to-weather mapper | Entry point (calls integrations) | Refactored |
| `src/nps_client.py` | NPS alerts client | Wrapped in integrations/alerts/ | Refactored |
| `src/nps_articles.py` | NPS articles client | Wrapped in integrations/content/ | Refactored |
| `app.py` | CLI entry point | Still works; CLI logic preserved | Unchanged |
| `ui_streamlit.py` | UI entry point | Still works; UI logic preserved | Unchanged |

---

## Known Limitations & Future Work

### Current Phase 1 Limitations

1. **ClimbingAdapter is a stub** – returns dummy scores. Full implementation in v1.
2. **No climbing alerts yet** – only NPS alerts available. Climbing alerts (permit changes, etc.) TBD.
3. **No climbing content indexing yet** – RAG works but needs climbing articles seeded.
4. **advisor_context.py still Yosemite-specific** – RAG queries hardcoded for hiking. Phase 2 fix.
5. **No skiing integration yet** – scaffolded but not implemented. v1.1+.

### How to Extend (for Future Phases)

- **To add skiing**: Create `SkiingAdapter`, define ski zones in config, add avalanche alerts integration.
- **To add climbing content**: Seed RAG with climbing articles, update ClimbingAdapter queries.
- **To add real climbing grades**: Integrate Mountain Project API in Phase 1.5.

---

## Success Criteria (Phase 1)

- [x] New objective-oriented API works without breaking hiking
- [x] Adapter pattern is clear and extensible
- [x] Integrations layer is decoupled from domain logic
- [x] Config supports multiple domains (hiking, climbing)
- [x] Migration guide is documented

---

## References

- **Design Document**: `SENDABLE_PLAN.md`, `SENDABLE_V1_SPEC.md`
- **Refactor Plan**: `REFACTOR_PLAN.md`
- **Code Structure**: See directory layout above

