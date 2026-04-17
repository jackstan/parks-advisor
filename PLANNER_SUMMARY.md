# Sendable Planner Implementation Summary

## What Was Built

A **deterministic planning orchestrator** that transforms user constraints into structured climbing/hiking recommendations.

## The Pipeline (6 Stages)

```
User Request → Generate Candidates → Evaluate (weather+scoring) 
→ Rank by Score → Select Primary+Backup → Generate Plans → Return Recommendation
```

## Files Created/Modified

### New Files
- `src/orchestration/planner.py` – **Main orchestrator** (394 lines)
  - `plan_outdoor_objective()` – Main entry point
  - `generate_candidates()` – Domain-specific candidate generation
  - `evaluate_candidates()` – Weather + scoring + ranking
  - `select_primary_and_backup()` – Pick top 2
  - `generate_plan()` – Create day-plan for each objective
  - `assemble_recommendation()` – Combine into final output

- `src/domain/recommendation_models.py` – **Output/intermediate models** (105 lines)
  - `RecommendationRequest` – User input
  - `ObjectiveCandidate` – Intermediate evaluated candidate
  - `DayPlan` – Single day itinerary
  - `PlannerRecommendation` – Final output with verdict, objectives, plans

### Modified Files
- `src/orchestration/__init__.py` – Updated to export planner functions
- `src/adapters/__init__.py` – Added `generate_plan()` abstract method + implementations for HikingAdapter and ClimbingAdapter
- `src/scoring.py` – Added `__all__` export for backward compat

## How It Works

### 1. Candidate Generation
- Climbing: Returns all climbing areas (RRG, Index, Bishop) matching filters
- Hiking: Returns Yosemite (or specified parks)

### 2. Evaluation
For each candidate:
- Fetch weather (Open-Meteo API)
- Fetch alerts (NPS API)
- Compute domain-specific scores (access, weather, crowd, risk)
- Sort by overall sendability score

### 3. Selection
- Primary = highest-scoring candidate
- Backup = 2nd-highest (or same if only 1)

### 4. Plan Generation
Each adapter (HikingAdapter, ClimbingAdapter) creates a domain-specific day plan with:
- Location & timing
- Suggested routes/trails
- Gear recommendations
- Weather-specific notes

### 5. Recommendation Assembly
Combines:
- Verdict (GO / CAUTION / NO-GO) based on score
- Primary & backup objectives
- Conditions summary (temp, wind, precip)
- Risk flags
- Explanation
- Full day plans

## Usage Example

```python
from datetime import datetime, timedelta
from src.domain.recommendation_models import RecommendationRequest
from src.orchestration import plan_outdoor_objective

request = RecommendationRequest(
    domain="climbing",
    location_ids=["rrg"],
    start_date=str(datetime.now().date()),
    end_date=str((datetime.now() + timedelta(days=1)).date()),
    grade_min="5.8",
    grade_max="5.11a",
    max_duration_hours=4.0,
    skill_level="intermediate",
)

rec = plan_outdoor_objective(request)
print(f"Verdict: {rec.sendability_verdict}")
print(f"Score: {rec.overall_sendability_score}")
print(f"Primary: {rec.primary_objective.location_name}")
print(f"Plan: {rec.primary_plan.location_name} at {rec.primary_plan.start_time}")
```

## Key Design Principles

✅ **Deterministic** – No LLM loop; clear decision pipeline  
✅ **Domain-Agnostic** – Orchestrator doesn't know about domains; adapters handle specifics  
✅ **Extensible** – Add skiing by creating 1 new adapter class  
✅ **Backward Compatible** – Old hiking flow still works  
✅ **Modular** – Each stage independently testable  
✅ **Error Resilient** – Failures don't crash the pipeline  

## Testing

```bash
python test_planner.py
```

Results:
- ✓ Climbing planning works (picks Red River Gorge)
- ✓ Hiking planning works (picks Yosemite)
- ✓ Verdicts based on weather scores (GO/CAUTION/NO-GO)
- ✓ Day plans generated with location-specific details

## Future Extensions

1. **UI Layer** – Create Streamlit UI to accept `RecommendationRequest` and display `PlannerRecommendation`
2. **LLM Integration** – Enhance explanation with GPT-4 (replace `_build_explanation()`)
3. **Skiing Domain** – Add `SkiingAdapter` + ski area config
4. **Advanced Scoring** – Refine weights for each domain
5. **Caching** – Cache weather/alerts to reduce API calls

## Files Reference

- **Orchestrator:** `src/orchestration/planner.py`
- **Models:** `src/domain/recommendation_models.py`
- **Adapters:** `src/adapters/__init__.py`
- **Documentation:** `PLANNER_IMPLEMENTATION.md` (comprehensive guide)
- **Test:** `test_planner.py`
