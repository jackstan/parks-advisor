# Quick Reference: New Architecture

## The 12-Bullet Plan (What Was Executed)

1. ✅ **Extract Generic Objective Model** → `src/domain/objective_models.py`
   - Base `Objective` with location_id, domain, constraints
   - Extensible for climbing, hiking, skiing subclasses

2. ✅ **Create Integrations Directory** → `src/integrations/`
   - `weather/` – domain-agnostic weather client
   - `alerts/` – abstract AlertProvider + NPS wrapper
   - `content/` – abstract ContentProvider + NPS wrapper

3. ✅ **Generalize Context Builder** → `src/orchestration/`
   - `build_objective_context()` – orchestrates data sources
   - `evaluate_objective()` – end-to-end evaluation

4. ✅ **Refactor Scoring** → `src/scoring/`
   - `generic.py` – domain-agnostic utilities
   - `hiking.py` – hiking-specific logic (placeholder)

5. ✅ **Create Config Factory** → `src/config.py`
   - Added `CLIMBING_AREAS` dict (Red, Index, Bishop)
   - `get_objective_location(domain, location_id)`
   - `get_locations_by_domain(domain)`

6. ✅ **Adapt Models** → `src/models.py`
   - Preserved for backward compat
   - Marked for deprecation (Phase 2)

7. ✅ **Decouple RAG** → `src/rag/`
   - No changes needed; already domain-agnostic
   - Index names parameterized for multi-domain

8. ✅ **Keep Existing UI/App** → `app.py`, `ui_streamlit.py`
   - Fully backward compatible
   - New code can opt-in to new API

9. ✅ **Refactor Alert System** → `src/integrations/alerts/`
   - `AlertProvider` abstract base
   - `NPSAlertProvider` concrete implementation
   - Ready for climbing alerts later

10. ✅ **Update LLM Advisor** → `src/advisor_llm.py`
    - No changes; already domain-agnostic
    - Adapters provide domain-specific prompts

11. ✅ **Create Domain Adapters** → `src/adapters/`
    - `ObjectiveAdapter` abstract base
    - `HikingAdapter` – wraps existing logic
    - `ClimbingAdapter` – stub for v1
    - Factory function: `get_adapter(domain)`

12. ✅ **Write Migration Guide** → `ARCHITECTURE_MIGRATION.md`
    - What changed and why
    - How to use new API
    - How to add new domains
    - Deprecation roadmap

---

## New API (Quick Examples)

### Create an Objective (Climbing Example)
```python
from src.domain.objective_models import Objective, UserConstraints

objective = Objective(
    objective_id="climb_001",
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
```

### Evaluate the Objective
```python
from src.orchestration import evaluate_objective
from src.config import get_objective_location

location = get_objective_location("climbing", "rrg")
recommendation = evaluate_objective(objective, location)

print(recommendation.verdict)  # "GO", "CAUTION", "NO-GO"
print(recommendation.overall_score)
print(recommendation.short_explanation)
```

### Get Available Locations
```python
from src.config import get_locations_by_domain

climbing_areas = get_locations_by_domain("climbing")
# {"rrg": "Red River Gorge", "index": "Index", "bishop": "Bishop"}

hiking_parks = get_locations_by_domain("hiking")
# {"yose": "Yosemite National Park", ...}
```

### Use Domain Adapter Directly
```python
from src.adapters import get_adapter

adapter = get_adapter("climbing")
scores = adapter.compute_scores(objective, weather_days, context)
```

---

## Adding a New Domain (Skiing Example)

### Step 1: Create Model (Optional)
```python
# src/domain/skiing_objective.py
from dataclasses import dataclass
from .objective_models import Objective

@dataclass
class SkiingObjective(Objective):
    aspect: str
    elevation_gain_ft: int
```

### Step 2: Create Adapter
```python
# Add to src/adapters/__init__.py
class SkiingAdapter(ObjectiveAdapter):
    def compute_scores(self, objective, weather_days, context):
        # skiing-specific scoring
        pass
    
    def format_context_for_llm(self, objective, scores, context):
        # skiing-specific formatting
        pass
    
    def get_system_message(self):
        return "You are a cautious ski advisor..."
    
    def parse_verdict(self, llm_output, scores):
        return "GO" if scores.trip_readiness_score >= 75 else "NO-GO"

# Update factory:
def get_adapter(domain: str):
    if domain == "skiing":
        return SkiingAdapter()
    # ... rest of factory
```

### Step 3: Add Config
```python
# In src/config.py
SKI_ZONES = {
    "tahoe": {"name": "Tahoe Backcountry", "lat": 39.0, "lon": -120.1, ...},
}

# Update factory:
def get_objective_location(domain, location_id):
    if domain == "skiing":
        return SKI_ZONES[location_id]
    # ... rest of factory
```

### Step 4: Create Integration (Optional)
```python
# src/integrations/avalanche/
class AvalancheProvider(AlertProvider):
    def get_alerts(self, location_id):
        # Fetch from USAC API
        pass
```

### Done!
New skiing objectives now work automatically. No changes to orchestrator, LLM layer, or core.

---

## Backward Compatibility Status

| Feature | Status | Note |
|---------|--------|------|
| `TripRequest` | ✅ Works | Old hiking code still works |
| `PARKS` dict | ✅ Works | NPS parks still available |
| `app.py` | ✅ Works | Hiking CLI unchanged |
| `ui_streamlit.py` | ✅ Works | Hiking UI unchanged |
| `build_trip_context()` | ✅ Works | Old hiking API unchanged |
| `advise_trip_with_explanation()` | ✅ Works | Old LLM API unchanged |

---

## File Structure Summary

```
src/
├── domain/                          [NEW] Domain models
│   ├── __init__.py
│   └── objective_models.py
├── orchestration/                   [NEW] Orchestration
│   ├── __init__.py
│   └── planner.py
├── integrations/                    [NEW] External integrations
│   ├── weather/
│   ├── alerts/
│   └── content/
├── scoring/                         [NEW] Scoring layer
│   ├── __init__.py
│   ├── generic.py
│   └── hiking.py
├── adapters/                        [NEW] Domain adapters
│   └── __init__.py
├── models.py                        [REFACTORED] Extended, marked deprecated
├── config.py                        [REFACTORED] Added CLIMBING_AREAS + factories
├── advisor_llm.py                   [UNCHANGED] Generic
├── advisor_context.py               [UNCHANGED] Will refactor Phase 2
├── weather_client.py                [UNCHANGED] Entry point (calls integrations)
├── scoring.py                       [UNCHANGED] Entry point (calls src/scoring/)
└── ... (other files unchanged)
```

---

## Documentation

- **Full Migration Guide**: `ARCHITECTURE_MIGRATION.md`
- **Refactor Rationale**: `REFACTOR_PLAN.md`
- **Summary**: `REFACTOR_SUMMARY.md` (this file)
- **Product Specs**: `SENDABLE_PLAN.md`, `SENDABLE_V1_SPEC.md`

---

## Testing Commands

```bash
# Test imports
python -c "from src.domain.objective_models import Objective; print('✓')"

# Test adapters
python -c "from src.adapters import get_adapter; print(get_adapter('climbing'))"

# Test config
python -c "from src.config import get_locations_by_domain; print(get_locations_by_domain('climbing'))"

# Test backward compat
python -c "from src.models import TripRequest; print('✓')"

# Run existing hiking app (should still work)
python app.py
streamlit run ui_streamlit.py
```

---

## Next Steps (Phases 2–3)

### Phase 2: Refactor Context & Prompts
- [ ] Move hiking RAG queries to HikingAdapter
- [ ] Adapt `advisor_context.py` to use adapters
- [ ] Create ClimbingAdapter prompt templates
- [ ] Test end-to-end with climbing objective

### Phase 3: Full Migration
- [ ] Mark `TripRequest` deprecated
- [ ] Migrate `app.py`, `ui_streamlit.py` to new API
- [ ] Remove backward-compat aliases
- [ ] Consolidate scoring logic

### v1.1: Domain Extensions
- [ ] Implement full ClimbingAdapter scoring
- [ ] Add climbing content to RAG
- [ ] Integrate Mountain Project API (read-only)
- [ ] Add SkiingAdapter skeleton

---

**Status**: Phase 1 complete. Architecture is ready for climbing-first development.

