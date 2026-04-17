# Planner Implementation Plan

## High-Level Strategy

Build a deterministic orchestrator that:
1. **Accepts** a user request with constraints (location, dates, grade, commitment)
2. **Generates** candidate objectives (e.g., 2-3 climbing areas that match constraints)
3. **Evaluates** each candidate with weather, scoring, and LLM context
4. **Ranks** candidates by overall sendability score
5. **Selects** primary (best) and backup (second-best)
6. **Assembles** a structured recommendation with plans and explanation

## Implementation Steps

### 1. Create Output Models (`src/domain/recommendation_models.py`)
- `RecommendationRequest` – input from user
- `ObjectiveCandidate` – intermediate representation during evaluation
- `PlannerRecommendation` – final structured output with primary, backup, explanation

### 2. Create Candidate Generator (`src/orchestration/planner.py`)
- `generate_candidates()` – returns 2-3 options matching user constraints
- For climbing: filter by location, grade range, approach time
- For hiking: filter by park, difficulty, duration
- Reusable for future domains

### 3. Create Evaluator (`src/orchestration/planner.py`)
- `evaluate_candidate()` – runs candidate through scoring pipeline
- Reuses existing: weather client, alerts, scoring, LLM
- Returns scores + explanation

### 4. Create Ranking & Selection (`src/orchestration/planner.py`)
- `rank_candidates()` – sort by overall_sendability_score
- `select_primary_and_backup()` – pick top 2

### 5. Create Plan Generator (`src/orchestration/planner.py`)
- `generate_plan()` – creates simple itinerary with timing, gear, notes
- Domain-agnostic structure, filled differently by adapters

### 6. Create Main Orchestrator (`src/orchestration/planner.py`)
- `plan_outdoor_objective()` – main entry point
- Ties everything together: generate → evaluate → rank → select → assemble

### 7. Update Models for Output (`src/models.py` or `src/domain/`)
- Add `PlannerRecommendation` dataclass
- Add `ObjectiveCandidate` dataclass
- Minimal; mostly reuse existing `Scores`, `WeatherDay`, etc.

### 8. Update Adapters (`src/adapters/__init__.py`)
- Each adapter implements `generate_candidates()` and `generate_plan()`
- HikingAdapter: suggest parks matching constraints
- ClimbingAdapter: suggest crags matching grade/approach

### 9. Create CLI/App Entry Point (`app.py` or new `app_planner.py`)
- Parse user input into `RecommendationRequest`
- Call `plan_outdoor_objective()`
- Pretty-print result

### 10. Optional: Add Tests
- Check `tests/` directory; if it exists, add planner tests

## Data Flow

```
User Request
  ↓
RecommendationRequest (constraints: location, dates, grade, etc.)
  ↓
generate_candidates(request) → [ObjectiveCandidate, ...]
  ↓
evaluate_candidate(candidate) → ObjectiveCandidate (with scores)
  ↓
rank_candidates([evaluated_candidates])
  ↓
select_primary_and_backup(ranked)
  ↓
generate_plan(primary), generate_plan(backup)
  ↓
assemble_recommendation(primary, backup, scores, context)
  ↓
PlannerRecommendation
  ├─ sendability_verdict
  ├─ primary_objective
  ├─ backup_objective
  ├─ conditions_summary
  ├─ sendability_scores
  ├─ risk_flags
  ├─ short_explanation
  ├─ primary_plan
  ├─ backup_plan
  └─ debug_context
```

## Reuse Strategy

- **Weather**: `src/integrations/weather/get_weather_for_location()`
- **Scoring**: Existing `src/scoring.py` (wrap to be domain-aware)
- **Alerts**: `src/integrations/alerts/nps.py` or domain-specific
- **LLM**: Existing `_call_llm_with_prompt()`, new domain-specific prompts
- **RAG**: Existing retriever, domain-specific queries

## Separation of Concerns

```
planner.py (orchestrator)
├── generate_candidates()        [domain-agnostic logic]
├── evaluate_candidate()         [reuses existing modules]
├── rank_candidates()            [simple sorting]
├── select_primary_and_backup()  [simple selection]
├── generate_plan()              [delegates to adapter]
└── plan_outdoor_objective()     [main entry point]

adapters/__init__.py
├── HikingAdapter.generate_candidates()
├── HikingAdapter.generate_plan()
├── ClimbingAdapter.generate_candidates()
├── ClimbingAdapter.generate_plan()
└── ... (skiing later)
```

## Extension Points (for Future Domains)

1. Each adapter implements `generate_candidates()` → no core changes
2. Each adapter implements `generate_plan()` → no core changes
3. Scoring and evaluation use adapters → automatic domain awareness
4. New domain = new adapter class + new config

## Success Criteria

- ✅ Can create a `RecommendationRequest` for climbing
- ✅ Planner generates 2-3 candidate crags matching constraints
- ✅ Evaluates each with weather, scoring, LLM
- ✅ Ranks and selects primary + backup
- ✅ Returns `PlannerRecommendation` with all required fields
- ✅ CLI or app entry point calls planner cleanly
- ✅ Backward compat: old hiking workflow still works
- ✅ Design supports skiing addition later

