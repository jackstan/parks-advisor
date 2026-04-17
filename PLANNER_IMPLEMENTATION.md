# Sendable Planner Orchestrator Implementation

## Overview

The planner orchestrator implements the first version of Sendable's planning loop: a deterministic, multi-stage system that transforms user constraints into structured recommendations.

### Core Pipeline

```
RecommendationRequest
       ↓
generate_candidates()        → List[ObjectiveCandidate]
       ↓
evaluate_candidates()        → List[ObjectiveCandidate] (scored, sorted)
       ↓
rank_candidates()            → Ranked list with .rank fields
       ↓
select_primary_and_backup()  → (primary, backup) candidates
       ↓
generate_plan()              → DayPlan (for each objective)
       ↓
assemble_recommendation()    → PlannerRecommendation
       ↓
PlannerRecommendation (verdict, scores, plans, explanation)
```

---

## Key Components

### 1. **Candidate Generation** (`generate_candidates()`)

**Purpose:** Generate all candidate objectives matching user constraints.

**Domain-Specific Logic:**

#### Climbing
- Filters climbing areas from `config.CLIMBING_AREAS` (v1: Red River Gorge, Index, Bishop)
- Optionally filters by `location_ids` from request
- Creates `Objective` with user constraints (grade range, approach time, commitment, skill level)

#### Hiking
- Filters parks from `config.PARKS`
- Defaults to Yosemite if no location specified
- Creates `Objective` with hiking-specific constraints

**Output:** List of `ObjectiveCandidate` with location metadata, but no scores yet.

---

### 2. **Candidate Evaluation** (`evaluate_candidates()`)

**Purpose:** Fetch weather, alerts, and compute sendability scores for each candidate.

**For Each Candidate:**
1. **Fetch Weather** → `get_weather_for_location(lat, lon, start_date, end_date)`
   - Returns `List[WeatherDay]` with temp, precipitation, wind, etc.
2. **Fetch Alerts** → `NPSAlertProvider().get_alerts(location_id)`
   - Returns active alerts for the location
3. **Get Domain Adapter** → `get_adapter(domain)`
   - Returns `HikingAdapter` or `ClimbingAdapter`
4. **Compute Scores** → `adapter.compute_scores(objective, weather, context)`
   - Returns `Scores` with breakdown: access, weather, crowd, risk, overall readiness
5. **Store Results** → Mutates candidate with weather, scores, overall_sendability_score

**Error Handling:** If evaluation fails, candidate gets default neutral score (50.0).

**Output:** List of evaluated candidates, sorted by `overall_sendability_score` (descending).

---

### 3. **Ranking** (`rank_candidates()`)

**Purpose:** Assign ranks to candidates by sendability score.

**Logic:**
- Sorts candidates by `overall_sendability_score` (highest first)
- Assigns `candidate.rank = 1, 2, 3, ...`

---

### 4. **Selection** (`select_primary_and_backup()`)

**Purpose:** Select top 2 candidates as primary and backup.

**Logic:**
- Primary = rank 1 (highest score)
- Backup = rank 2 (or same as primary if only 1 candidate)

---

### 5. **Plan Generation** (`generate_plan()`)

**Purpose:** Generate domain-specific day plans.

**HikingAdapter.generate_plan():**
- Returns `DayPlan` with:
  - Day label: "Saturday" (primary) or "Sunday" (backup)
  - Location name
  - Start time: 8:00 AM
  - Trails/routes: suggestions based on skill level
  - Duration: from constraints
  - Approach time: from constraints
  - Gear: hiking-specific recommendations
  - Notes: weather/condition-specific advice

**ClimbingAdapter.generate_plan():**
- Returns `DayPlan` with:
  - Day label: "Saturday" (primary) or "Sunday" (backup)
  - Location name
  - Start time: 9:00 AM
  - Routes: grade suggestions
  - Duration: from constraints
  - Approach time: from constraints
  - Gear: climbing-specific (rack, quickdraws, belay gear)
  - Notes: rock condition forecasts

---

### 6. **Recommendation Assembly** (`assemble_recommendation()`)

**Purpose:** Combine selected objectives, plans, and scores into final `PlannerRecommendation`.

**Verdict Determination:**
- `score >= 75` → "GO"
- `55 <= score < 75` → "CAUTION"
- `score < 55` → "NO-GO"

**Conditions Summary:** Extracted from primary's weather data:
- Temperature (°F)
- Precipitation probability
- Wind speed (mph)
- Rock condition (dry/damp/wet)
- Forecast confidence (based on window size)

**Scores Dictionary:** Breakdown of component scores (access, weather, crowd, risk, overall).

**Explanation:** Short narrative based on verdict and score.

---

## Main Entry Point

```python
def plan_outdoor_objective(request: RecommendationRequest) -> PlannerRecommendation:
    """
    Main orchestrator: end-to-end planning.
    
    Args:
        request: RecommendationRequest with domain, dates, constraints
    
    Returns:
        PlannerRecommendation with verdict, objectives, plans, explanation
    """
```

**Usage Example:**

```python
from datetime import datetime, timedelta
from src.domain.recommendation_models import RecommendationRequest
from src.orchestration import plan_outdoor_objective

today = datetime.now().date()
tomorrow = today + timedelta(days=1)

request = RecommendationRequest(
    domain="climbing",
    location_ids=["rrg"],
    start_date=str(today),
    end_date=str(tomorrow),
    grade_min="5.8",
    grade_max="5.11a",
    max_duration_hours=4.0,
    skill_level="intermediate",
)

recommendation = plan_outdoor_objective(request)

print(f"Verdict: {recommendation.sendability_verdict}")
print(f"Score: {recommendation.overall_sendability_score}")
print(f"Primary: {recommendation.primary_objective.location_name}")
print(f"Plan: {recommendation.primary_plan.start_time} at {recommendation.primary_plan.location_name}")
```

---

## Data Models

### RecommendationRequest
```python
@dataclass
class RecommendationRequest:
    domain: str                            # "climbing", "hiking", "skiing"
    location_ids: Optional[List[str]]      # Specific locations; if None, auto-suggest
    start_date: str                        # ISO format "2024-01-20"
    end_date: str                          # ISO format "2024-01-21"
    grade_min: Optional[str]               # "5.9" for climbing
    grade_max: Optional[str]               # "5.11a"
    max_duration_hours: Optional[float]    # 4.0
    max_approach_minutes: Optional[int]    # 30
    commitment_level: str                  # "flexible", "committed"
    skill_level: str                       # "beginner", "intermediate", "advanced"
    partner_count: Optional[int]
    custom_notes: Optional[str]
```

### PlannerRecommendation
```python
@dataclass
class PlannerRecommendation:
    sendability_verdict: str                   # "GO", "CAUTION", "NO-GO"
    overall_sendability_score: float           # 0–100
    
    primary_objective: ObjectiveCandidate      # Top-ranked candidate
    backup_objective: ObjectiveCandidate       # 2nd-ranked candidate
    
    conditions_summary: Dict[str, Any]         # {temperature_f, wind_mph, ...}
    sendability_scores: Dict[str, float]       # {access, weather, crowd, risk, overall}
    
    risk_flags: List[str]                      # ["wind_strong", "precip_high"]
    short_explanation: str                     # 1–2 sentences
    detailed_explanation: Optional[str]        # LLM-generated
    
    primary_plan: DayPlan                      # Full itinerary
    backup_plan: DayPlan
    
    debug_context: Dict[str, Any]              # For transparency
```

---

## Domain Adapter Interface

All domain adapters implement `ObjectiveAdapter` with these methods:

```python
class ObjectiveAdapter(ABC):
    @abstractmethod
    def compute_scores(objective, weather_days, context) -> Scores
    
    @abstractmethod
    def format_context_for_llm(objective, scores, context) -> str
    
    @abstractmethod
    def get_system_message() -> str
    
    @abstractmethod
    def parse_verdict(llm_output, scores) -> str
    
    @abstractmethod
    def generate_plan(objective, scores, weather_days, is_primary) -> DayPlan
```

---

## Integration Points

### Weather Integration
```python
from src.integrations.weather import get_weather_for_location

weather_days = get_weather_for_location(
    lat=38.5, lon=-83.7,
    start_date="2024-01-20", end_date="2024-01-21",
    location_id="rrg"
)
```

### Alerts Integration
```python
from src.integrations.alerts.nps import NPSAlertProvider

alerts = NPSAlertProvider().get_alerts("yose")
```

### Config Integration
```python
from src.config import CLIMBING_AREAS, PARKS, get_objective_location

location_meta = get_objective_location("climbing", "rrg")
# Returns: {"name": "Red River Gorge", "lat": 38.5, "lon": -83.7, ...}
```

---

## Error Handling

1. **Missing Location Metadata:** If lat/lon missing, candidate skipped with warning
2. **Evaluation Failures:** Candidate gets default score (50.0), logged but doesn't crash
3. **No Candidates:** Pipeline raises `ValueError("No candidates found for {domain}")`
4. **Invalid Domain:** Raises `ValueError("Unknown domain: {domain}")`

---

## Future Extensions

### Phase 2: Add Skiing Domain
1. Create `SkiingAdapter` implementing `ObjectiveAdapter`
2. Add ski areas to `config.SKIING_AREAS`
3. Register in `get_adapter()` factory
4. No changes needed to orchestrator—it's already domain-agnostic

### Phase 3: LLM Integration
1. Replace `_build_explanation()` with full LLM call
2. Use `adapter.format_context_for_llm()` for rich context
3. Use `adapter.get_system_message()` for domain-specific persona
4. Call `advisor_llm._call_llm_with_prompt()` for detailed explanation

### Phase 4: UI Integration
1. Create `app_planner.py` or update `app.py`
2. Parse user input → `RecommendationRequest`
3. Call `plan_outdoor_objective(request)`
4. Pretty-print `PlannerRecommendation` in Streamlit

---

## Testing

Run the test suite:
```bash
cd /Users/jackstanger/Sendable
python test_planner.py
```

Expected output:
```
✓ Climbing recommendation generated
  Verdict: GO
  Score: 75.0
  Primary: Red River Gorge
  Backup: Red River Gorge
  Explanation: Excellent window for Red River Gorge...

✓ Hiking recommendation generated
  Verdict: NO-GO (or CAUTION/GO depending on weather)
  Score: 50.0+
  Primary: Yosemite National Park
```

---

## Code Organization

```
src/
├── orchestration/
│   ├── __init__.py              (exports plan_outdoor_objective)
│   └── planner.py               (main orchestrator functions)
├── domain/
│   ├── objective_models.py       (base Objective, UserConstraints)
│   └── recommendation_models.py  (RecommendationRequest, PlannerRecommendation)
├── adapters/
│   └── __init__.py               (HikingAdapter, ClimbingAdapter, get_adapter())
├── integrations/
│   ├── weather/__init__.py       (get_weather_for_location)
│   └── alerts/nps.py             (NPSAlertProvider)
├── config.py                     (CLIMBING_AREAS, PARKS, factories)
└── scoring.py                    (compute_scores for backward compat)
```

---

## Key Achievements

✅ **Deterministic Orchestrator:** Clear pipeline from request → recommendation  
✅ **Domain-Agnostic Core:** Add climbing, skiing, or other domains without modifying orchestrator  
✅ **Backward Compatible:** Old hiking app still works via `HikingAdapter`  
✅ **Modular Design:** Each stage (generate, evaluate, rank, plan) is independently testable  
✅ **Error Resilient:** Failures in one candidate don't crash the pipeline  
✅ **Extensible:** New adapters, new scoring logic, new integrations all plug in cleanly  

---

## Next Steps

1. **Implement UI** (`app_planner.py`): Accept user input, display recommendations
2. **Add LLM Integration**: Call GPT-4 for detailed explanations and multi-objective planning
3. **Expand Skiing**: Create `SkiingAdapter`, add ski areas to config
4. **Improve Scoring**: Refine domain-specific weights and thresholds
5. **Add Caching**: Cache weather and alerts to reduce API calls
