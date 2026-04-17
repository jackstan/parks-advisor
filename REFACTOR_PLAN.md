# Architecture Refactor: Park-Centric → Objective-Centric

## Summary of Planned Changes (12 Bullets)

### 1. **Extract Generic Objective Model** (`src/domain/objective_models.py`)
   - Create a base `Objective` dataclass with fields: `objective_id`, `location_id` (generic), `start_date`, `end_date`, `user_constraints`.
   - Move `TripRequest` → archive/reference only. Create `HikingObjective` and `ClimbingObjective` as concrete subclasses.
   - Keep shared fields in base; domain-specific fields (e.g., `grade`, `approach_time`) in subclasses.
   - **Rationale**: Unify the concept of "what are we evaluating?" across domains without losing climbing/skiing-specific metadata.

### 2. **Create Integrations Directory Structure** (`src/integrations/`)
   - Set up subdirs: `weather/`, `alerts/`, `content/`, `climbing/`, `skiing/` (stub).
   - Move `weather_client.py` → `integrations/weather/client.py` (rename `get_weather_for_trip` → `get_weather_for_location`).
   - Move NPS clients (`nps_client.py`, `nps_articles.py`, `nps_things_to_do.py`) → `integrations/content/nps_client.py`.
   - Create `integrations/alerts/base.py` and `integrations/alerts/nps.py` (wrapper).
   - Create `integrations/climbing/` stub for future Mountain Project / 8a.nu clients.
   - **Rationale**: Organizes external dependencies by domain; makes it clear what's pluggable and what's NPS-specific.

### 3. **Generalize Context Builder** (`src/orchestration/objective_context.py`)
   - Rename `build_trip_context()` → `build_objective_context()` (keep legacy wrapper).
   - Replace hardcoded park-specific logic with pluggable content adapters.
   - Remove Yosemite-specific RAG queries; make queries generated from objective metadata.
   - Accept an optional `domain_adapter` parameter to specialize behavior (e.g., climbing vs hiking).
   - **Rationale**: Decouples context assembly from the hiking domain.

### 4. **Refactor Scoring to Support Multiple Domains** (`src/scoring/`)
   - Create `scoring/generic.py` with domain-agnostic scoring utilities (temp conversion, wind penalties, etc.).
   - Create `scoring/hiking.py` with hiking-specific weights/thresholds.
   - Create `scoring/climbing.py` (stub for v1.1; referenced by ClimbingAdapter).
   - Update `src/scoring.py` → refactor as thin wrapper or dispatcher.
   - **Rationale**: Makes the scoring logic composable and extensible without rewriting.

### 5. **Create Config Factory Pattern** (`src/config.py` refactor)
   - Keep `PARKS` dict for backward compat, but add factory function: `get_objective_location(domain, location_id) → dict`.
   - Add `CLIMBING_AREAS` dict (minimal v1: Red, Index, Bishop).
   - Add `get_locations_by_domain(domain)` for UI dropdowns.
   - Mark NPS-specific functions as `_nps_*` (private) to signal deprecation.
   - **Rationale**: Gradual migration toward domain-agnostic config without breaking existing code.

### 6. **Adapt Models for Objective-Oriented Use** (`src/models.py` refactor)
   - Rename `park_code` field → `location_id` in `WeatherDay` and `Scores` (keep aliases for backward compat).
   - Add `location_type` (e.g., "climbing_area", "national_park") where needed.
   - Keep `Park`, `TripRequest` as-is for backward compat; mark as "@deprecated" in docstrings.
   - **Rationale**: Gradual, non-breaking migration; old code still works, new code uses cleaner names.

### 7. **Decouple RAG from NPS** (`src/rag/`, `src/integrations/content/`)
   - RAG index/retrieval logic stays in `rag/`; it's domain-agnostic.
   - Move article/content fetching to `integrations/content/` with adapters.
   - Parameterize index names: `park_{location_id}` → `location_{location_id}_{domain}`.
   - **Rationale**: RAG is reusable; content sources are pluggable.

### 8. **Keep Existing UI/App Entry Points Backward Compatible**
   - `app.py` and `ui_streamlit.py` keep using `TripRequest` for now.
   - Create new entry points: `app_climbing.py` and `ui_streamlit_climbing.py` as thin wrappers.
   - Both point to the new objective orchestration layer.
   - **Rationale**: Enables shipping climbing features without breaking the hiking workflow.

### 9. **Refactor Alert System** (`src/integrations/alerts/`)
   - Move `nps_client.py` alert logic to `integrations/alerts/nps.py`.
   - Create `integrations/alerts/base.py` with abstract `AlertProvider` interface.
   - Climbing adapter can later inject climbing-specific alert providers (road closures, permits).
   - **Rationale**: Prepares for non-NPS alert sources (climbing areas).

### 10. **Update LLM Advisor for Objective Pattern** (`src/advisor_llm.py` light refactor)
   - Keep core LLM call as-is; it's domain-agnostic.
   - Refactor prompt builder to accept objective + domain context, not just TripRequest.
   - Move hiking-specific prompts to `src/integrations/climbing/prompts.py` later.
   - **Rationale**: Keeps the LLM layer generic; domain-specific framing lives in domain adapters.

### 11. **Create Lightweight Domain Adapters** (`src/adapters/climbing.py`, stub)
   - Climbing adapter implements `compute_scores()`, `format_context_for_llm()`, etc.
   - Provides climbing-specific system message, RAG query templates.
   - Decouples climbing logic from core orchestration.
   - **Rationale**: Makes it trivial to add skiing later (new adapter, same orchestration).

### 12. **Write Migration Guide** (`ARCHITECTURE_MIGRATION.md`)
   - Document what changed and why.
   - Show migration path for old code (TripRequest → ObjectiveRequest).
   - List which files are deprecated, renamed, or refactored.
   - Include examples of using new objective-oriented API.
   - **Rationale**: Helps future devs understand the design.

---

## Implementation Notes

### What's Safe to Change Now
- Create new modules (no breaking changes).
- Refactor internal function names (e.g., `get_weather_for_trip` → `get_weather_for_location`), keep aliases.
- Move files into subdirectories; update imports.
- Add new fields to models; mark old fields as `@deprecated`.

### What We Preserve (for backward compat)
- `TripRequest` dataclass (used by hiking app).
- `src/weather_client.py` entry point (with deprecation alias).
- `PARKS` config dict.
- Existing app.py, ui_streamlit.py workflows.

### What We Defer (too premature for v1)
- Full rewrite of scoring engine (extend, don't replace).
- Multi-day trip orchestration (keep single-trip logic).
- Real Mountain Project / 8a.nu integration (stub adapters only).
- Full DAG-based orchestration (keep sequential, simple).

---

## Success Criteria
1. New climbing-first code uses objective-oriented API.
2. Old hiking code still works (no breaking changes).
3. RAG/weather/LLM layers are truly domain-agnostic.
4. Adding a new domain (e.g., skiing) requires <50 lines of new model code + 1 adapter.
5. All refactored files have clear docstring comments explaining new architecture.

