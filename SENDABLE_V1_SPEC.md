# Sendable v1 Product Specification

**Date**: April 2026  
**Scope**: Climbing-first decision agent for single objectives  
**MVP Target**: 2-week implementation  

---

## 1. User Inputs (v1 Form)

### Primary Inputs

Users will specify a climbing objective via Streamlit form with these required fields:

| Field | Type | Options / Constraints | Example |
|-------|------|----------------------|---------|
| **Climbing Area** | Select | "Red River Gorge", "Index", "Bishop" (hardcoded 3 in v1) | "Red River Gorge" |
| **Grade Range** | Text Input (or select) | "5.9-5.10a", "5.10b-5.10d", "5.11a+", "V4-V5", etc. | "5.10" |
| **Climb Type** | Select | "Sport", "Trad", "Boulder", "Mixed" | "Sport" |
| **Trip Dates** | Date Range | Start and end dates (within next 16 days) | Apr 19–21 |
| **Approach Time Tolerance** | Select | "<30min", "30-60min", "1-2hr", "2-3hr", "3+hr" | "1-2hr" |

### Secondary / Optional Inputs

| Field | Type | Notes |
|-------|------|-------|
| **Preferred Commitment Level** | Select (Climbing-centric) | "Walk-up", "Half-day", "Full-day", "Multi-day" | Not yet used in v1 scoring; seed for v1.1 |
| **Weather Priority** | Select | "Any weather", "Dry rock preferred", "Avoid storms" | Influences LLM framing, not scoring weight |
| **Partner Availability** | Text (optional) | "Solo", "2 climbers", "Group of 4" | Informational for LLM context only |

---

## 2. Output Schema (v1)

### Top-Level Response Object

```json
{
  "sendability_verdict": "GO" | "CAUTION" | "NO-GO",
  "primary_objective": {
    "crag_name": "Red River Gorge",
    "crag_id": "rrg",
    "route_names": ["Motherlode", "Screwdriver"],
    "grade_suggested": "5.10a",
    "approach_minutes": 45,
    "exposure_level": "moderate"
  },
  "backup_objective": {
    "crag_name": "Index",
    "crag_id": "index",
    "route_names": ["Kangaroo Crack", "Sunday Pillar"],
    "grade_suggested": "5.9+",
    "approach_minutes": 30,
    "exposure_level": "low"
  },
  "conditions_summary": {
    "temperature_f": 72,
    "precipitation_probability": 15,
    "wind_mph": 12,
    "humidity_percent": 65,
    "rock_condition": "dry",
    "forecast_confidence": "high"
  },
  "sendability_scores": {
    "grade_alignment": 85,
    "rock_condition_score": 80,
    "weather_score": 78,
    "exposure_risk": 70,
    "overall_sendability": 78
  },
  "risk_flags": [
    "wind_moderate",
    "crowd_likely_weekend"
  ],
  "short_explanation": "Good weekend window for 5.10s. Dry rock, moderate winds. Approach trails clear. Consider lower-grade backup at Index if conditions are marginal on-site.",
  "primary_plan": {
    "day": "Saturday",
    "crag": "Red River Gorge",
    "start_time": "8:00 AM",
    "primary_routes": ["Motherlode (5.10a)", "Screwdriver (5.10a)"],
    "expected_duration_hours": 5,
    "gear": "Sport rack, 10x quickdraws",
    "notes": "Approach wet until ~8:30 AM; start after drying."
  },
  "backup_plan": {
    "day": "Saturday (fallback)",
    "crag": "Index",
    "start_time": "10:00 AM",
    "primary_routes": ["Kangaroo Crack (5.9+)", "Sunday Pillar (5.9)"],
    "expected_duration_hours": 3,
    "gear": "Trad rack (set of cams #0.5-2, stoppers)",
    "notes": "Lower commitment; good if RRG too crowded or wet."
  },
  "debug_context": {
    "weather_forecast": [...],
    "rag_sources": [...],
    "scoring_details": {...},
    "llm_reasoning": "..."
  }
}
```

### Streamlit UI Display

The UI will show this information in layers:

```
┌────────────────────────────────────────────────────────────┐
│ 🪨 SENDABILITY VERDICT                                     │
│                                                            │
│ ✅ GO (78/100)                                             │
│    "Good window for 5.10s at Red River Gorge this weekend" │
├────────────────────────────────────────────────────────────┤
│ PRIMARY OBJECTIVE                                          │
│ Red River Gorge — 5.10a Sport                             │
│ Routes: Motherlode, Screwdriver                           │
│ Approach: 45min | Exposure: Moderate                      │
├────────────────────────────────────────────────────────────┤
│ BACKUP OBJECTIVE                                           │
│ Index — 5.9+ Trad                                          │
│ Routes: Kangaroo Crack, Sunday Pillar                     │
│ Approach: 30min | Exposure: Low                           │
├────────────────────────────────────────────────────────────┤
│ CONDITIONS SUMMARY                                         │
│ 72°F | 15% precip | 12 mph wind | Dry rock               │
├────────────────────────────────────────────────────────────┤
│ RISK FLAGS                      ⚠️ Wind | 🌦️ Weekend crowd  │
├────────────────────────────────────────────────────────────┤
│ SENDABILITY BREAKDOWN                                      │
│ Grade Fit:         85/100 ████████░░                      │
│ Rock Condition:    80/100 ████████░░                      │
│ Weather:           78/100 ███████░░░                      │
│ Exposure Risk:     70/100 ███████░░░                      │
├────────────────────────────────────────────────────────────┤
│ PRIMARY PLAN                                               │
│ Saturday: RRG, start 8am, 5 hours, bring sport rack      │
│ Routes: Motherlode → Screwdriver                          │
│ Note: Approach wet until 8:30am                           │
├────────────────────────────────────────────────────────────┤
│ BACKUP PLAN                                                │
│ Saturday (fallback): Index, 10am, 3 hours, trad rack     │
│ Routes: Kangaroo Crack → Sunday Pillar                    │
│ Note: Use if RRG too crowded or marginal                  │
├────────────────────────────────────────────────────────────┤
│ [Expand for detailed reasoning from LLM advisor]          │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model

### 3.1 Climbing Area (Core Reference Data)

Location in codebase: **`src/config.py`** (refactored)

```python
@dataclass
class ClimbingArea:
    area_id: str                    # e.g., "rrg", "index", "bishop"
    name: str                       # e.g., "Red River Gorge"
    state: str                      # e.g., "KY"
    lat: float
    lon: float
    elevation_ft: Optional[int]     # e.g., 800
    timezone: str                   # e.g., "America/Chicago"
    
    # Climbing-specific metadata
    primary_rock_type: str          # "sandstone", "granite", "basalt", "limestone"
    primary_climb_types: List[str]  # ["sport", "trad", "boulder"]
    grade_range: str                # "5.7-5.13a" (typical for area)
    
    # Access & logistics
    approach_difficulty: str        # "easy", "moderate", "strenuous"
    is_established: bool            # Whether area has official crags/routes
    permit_required: bool
    best_seasons: List[str]         # ["spring", "fall"] 
    crowd_tendency: str             # "low", "moderate", "high"
    
    # Historical conditions reference
    typical_wetness_after_rain_hours: int  # e.g., 24 (dries in 24 hours)
    typical_freeze_temp_f: float    # e.g., 32 (when rock freezes over night)
```

**v1 Config Example** (`src/config.py`):

```python
CLIMBING_AREAS = {
    "rrg": ClimbingArea(
        area_id="rrg",
        name="Red River Gorge",
        state="KY",
        lat=38.5,
        lon=-83.7,
        elevation_ft=800,
        timezone="America/Chicago",
        primary_rock_type="sandstone",
        primary_climb_types=["sport", "trad"],
        grade_range="5.6-5.12c",
        approach_difficulty="moderate",
        is_established=True,
        permit_required=False,
        best_seasons=["spring", "fall"],
        crowd_tendency="high",
        typical_wetness_after_rain_hours=24,
        typical_freeze_temp_f=32,
    ),
    # ... Index, Bishop
}
```

### 3.2 Climbing Objective (User Request)

Location in codebase: **`src/objectives/climbing_objective.py`** (new)

```python
@dataclass
class ClimbingObjective:
    # Identity
    objective_id: str               # UUID or auto-generated
    user_id: Optional[str]          # For future multi-user
    
    # What & Where
    area_id: str                    # "rrg", "index", "bishop"
    grade_min: str                  # "5.9"
    grade_max: str                  # "5.11a"
    climb_type: str                 # "sport", "trad", "boulder", "mixed"
    
    # When
    start_date: str                 # ISO format
    end_date: str                   # ISO format
    
    # Constraints & Preferences
    approach_time_tolerance_min: int  # 0 (any)
    approach_time_tolerance_max: int  # e.g., 180 (3 hours)
    commitment_level: str           # "walk-up", "half-day", "full-day", "multi-day"
    
    # Context (informational)
    partner_count: Optional[int]    # e.g., 1 (solo), 2 (partner), etc.
    weather_priority: str           # "any", "dry_preferred", "avoid_storms"
    notes: Optional[str]            # User's additional notes
```

### 3.3 Route / Crag Objective

Location in codebase: **`src/objectives/climbing_objective.py`** (new)

```python
@dataclass
class ClimbingRoute:
    """
    A specific climbing route within a crag.
    Seeded from manual data or Mountain Project API (v1.1).
    """
    route_id: str                   # e.g., "rrg_motherlode"
    area_id: str                    # reference to parent
    route_name: str                 # e.g., "Motherlode"
    grade: str                      # "5.10a"
    grade_facet: str                # "5.10a sport" or "5.8 trad"
    protection_quality: str         # "bolted", "solid_gear", "sparse_gear", "mixed"
    exposure_level: str             # "low", "moderate", "high", "extreme"
    pitch_count: int                # 1 for single-pitch, 2+ for multi
    approach_minutes: int           # e.g., 45
    height_feet: Optional[int]      # e.g., 120
    description: Optional[str]      # Route beta
    recent_conditions: Optional[str]  # "Dry as of April 15"
    url: Optional[str]              # MP or 8a link
```

### 3.4 User Constraint / Recommendation Pair

This is what the app must match: user constraints → recommended routes.

```python
@dataclass
class RecommendedObjective:
    """
    A proposed objective that matches user constraints.
    Returned by the matching/selection logic.
    """
    ranking: int                    # 1 (primary), 2 (backup), 3, etc.
    area_id: str
    area_name: str
    route_ids: List[str]           # 1–3 routes for a session
    route_names: List[str]
    grades: List[str]              # e.g., ["5.10a", "5.10b"]
    climb_type: str
    avg_approach_minutes: float
    primary_exposure_level: str     # dominant exposure
    reason_selected: str            # "Matches your grade and approach time"
    predicted_condition_fit: float  # 0–100: how well weather aligns
```

### 3.5 Conditions Summary

Location in codebase: **`src/models.py`** (extend `WeatherDay`)

```python
@dataclass
class ClimbingConditionsSummary:
    """
    Weather + rock-specific conditions for climbing context.
    Derived from WeatherDay + area metadata.
    """
    # Weather
    temp_high_f: float
    temp_low_f: float
    humidity_percent: float
    wind_speed_max_mph: float
    precip_probability: float
    precip_mm: float
    thunderstorm_probability: float
    
    # Rock condition (inferred from weather + historical data)
    rock_condition: str             # "dry", "damp", "wet", "frozen"
    time_until_dry_hours: Optional[int]  # If wet, when will it dry?
    freeze_risk: bool               # Will rock freeze overnight?
    
    # Forecast metadata
    forecast_confidence: str        # "high" (0–3 days), "medium" (4–7), "low" (8+)
    date_of_forecast: str           # ISO format
```

### 3.6 Sendability Scores

Location in codebase: **`src/models.py`** (extend or new `ClimbingScores`)

```python
@dataclass
class ClimbingScores:
    """
    Climbing-specific scoring breakdown.
    These feed into an overall sendability verdict.
    """
    # Component scores (0–100)
    grade_alignment: float          # User grade vs recommended grade fit
    rock_condition_score: float     # Is the rock in climbable condition?
    weather_score: float            # Temperature, wind, precipitation ok?
    exposure_risk: float            # Thunderstorm, approach hazard risk (higher = more risk)
    approach_feasibility: float     # Can approach be done safely/comfortably?
    
    # Aggregate
    sendability_score: float        # Weighted average; main verdict driver
    
    # Metadata
    risk_flags: List[str]           # "wind_strong", "wet_rock", "crowd_likely", etc.
    notes: List[str]                # Human-readable explanations
    
    # For explainability
    weights_used: Dict[str, float]  # {"grade_alignment": 0.25, ...}
```

### 3.7 Recommendation Output

Location in codebase: **`src/advisor_llm.py`** (refactor)

```python
@dataclass
class SendableRecommendation:
    """
    The final output from the advisor orchestrator.
    Combines scores, context, objectives, and LLM reasoning.
    """
    # Verdict
    sendability_verdict: str        # "GO", "CAUTION", "NO-GO"
    sendability_score: float        # 0–100
    
    # Objectives
    primary_objective: RecommendedObjective
    backup_objective: RecommendedObjective
    
    # Conditions
    conditions_summary: ClimbingConditionsSummary
    sendability_scores: ClimbingScores
    
    # Plans
    primary_plan: DayPlan
    backup_plan: DayPlan
    
    # Reasoning
    short_explanation: str          # 1–2 sentences
    detailed_explanation: str       # LLM-generated paragraph
    
    # Debug
    llm_prompt_used: Optional[str]  # For transparency
    rag_sources: List[str]          # Documents used in context
```

```python
@dataclass
class DayPlan:
    """
    A simple itinerary for a climbing day.
    """
    day_label: str                  # "Saturday", "Sunday"
    area_name: str
    start_time: str                 # "8:00 AM"
    route_names: List[str]
    expected_duration_hours: float
    gear_required: str              # e.g., "Sport rack, 10x quickdraws"
    driving_time_hours: Optional[float]  # From metro area
    approach_minutes: int
    notes: str                      # Conditions-specific guidance
```

---

## 4. Scoring Dimensions & Decision Thresholds

### 4.1 Scoring Dimensions

All scores are normalized to 0–100, where:
- **Sendability component scores**: Higher = better conditions
- **Risk scores** (e.g., exposure_risk): Higher = more risk (inverted when aggregating)

| Dimension | Weight | Formula | Thresholds |
|-----------|--------|---------|-----------|
| **Grade Alignment** | 25% | Match user grade_min/max vs recommended; penalty if mismatch | 100: exact fit, 70: 1 grade harder, 40: 2+ grades harder |
| **Rock Condition** | 20% | Inferred from weather + area drying rate; "dry" = 100, "wet" = 50, "frozen" = 30 | See matrix below |
| **Weather Score** | 30% | Temp comfort, wind, precip (reuse logic from `scoring.py`) | See matrix below |
| **Exposure Risk** | 15% | Thunderstorm prob + route exposure level; lower = safer | 100: no storm risk + low exposure, 30: high storm + high exposure |
| **Approach Feasibility** | 10% | Road access, approach weather, user time constraint | 100: dry, clear, within time; 50: marginal; 0: impassable |

**Rock Condition Matrix** (driving `rock_condition_score`):

| Weather Event | Hours Since Rain | Area Drying Rate | Condition | Score |
|---------------|------------------|------------------|-----------|-------|
| Dry | N/A | N/A | Dry | 100 |
| Rain | 0–4 hrs | 24-hr area | Wet | 50 |
| Rain | 4–12 hrs | 24-hr area | Damp | 75 |
| Rain | 12–24 hrs | 24-hr area | Drying | 85 |
| Overnight freeze | Temp < 32°F | Any | Frozen | 30 |
| Sun exposure after rain | 8+ hrs | 24-hr area | Dry | 100 |

**Weather Score Matrix** (reuse from `scoring.py`, adapted):

| Metric | Range | Score |
|--------|-------|-------|
| **Temperature** | 50–75°F (ideal for climbing) | 100 |
| **Temperature** | 40–50°F or 75–85°F | 80 |
| **Temperature** | 30–40°F or 85–95°F | 60 |
| **Temperature** | <30°F or >95°F | 20 |
| **Wind** | <10 mph | +0 penalty |
| **Wind** | 10–20 mph | –10 penalty |
| **Wind** | 20–30 mph | –20 penalty |
| **Wind** | >30 mph | –40 penalty (severe) |
| **Precip Probability** | <20% | +0 |
| **Precip Probability** | 20–50% | –10 |
| **Precip Probability** | 50–80% | –25 |
| **Precip Probability** | >80% | –50 (very risky) |
| **Thunderstorm Prob** | >20% + high exposure | Add "thunderstorm_risk" flag; –15 to weather score |

**Exposure Risk Score** (inverse logic):

```
exposure_risk_score = 100 - (route_exposure_points + thunderstorm_points)

where:
  route_exposure_points = 10 (low) | 30 (moderate) | 60 (high) | 80 (extreme)
  thunderstorm_points = 0 (<10% prob) | 10 (10–20%) | 25 (20–40%) | 50 (>40%)
```

### 4.2 Sendability Verdict Decision Tree

```
Overall Sendability Score = 
  0.25 * grade_alignment +
  0.20 * rock_condition_score +
  0.30 * weather_score +
  0.15 * (100 - exposure_risk_score) +  # invert so lower risk = higher score
  0.10 * approach_feasibility

VERDICT LOGIC:
  if sendability_score >= 75 AND no "severe_risk" flags:
    verdict = "GO"
    
  else if sendability_score >= 60 AND no "critical_risk" flags:
    verdict = "CAUTION"
    LLM refines: "Doable, but watch for [specific risk]"
    
  else:
    verdict = "NO-GO"
    LLM refines: "Not ideal today; consider backup objective or wait"

CRITICAL RISK FLAGS (trigger NO-GO):
  - "thunderstorm_high_probability" (>40% + high exposure)
  - "rock_impossible" (frozen, or 100% precip prob)
  - "approach_unsafe" (road closures, severe weather on approach)
  
SEVERE RISK FLAGS (push CAUTION, lower score):
  - "wet_rock" (damp/wet condition)
  - "wind_strong" (>25 mph)
  - "temperature_extreme" (<30°F or >95°F)
  - "crowd_likely" (weekend in high-crowd area)
```

### 4.3 Risk Flags (Climbing-Specific)

These are flags that inform verdict and LLM reasoning:

| Flag | Triggered When | LLM Framing |
|------|----------------|-----------|
| `grade_mismatch` | User grade > recommended by 2+ | "You may find this harder than expected; start with easier routes." |
| `wet_rock` | Rock condition < "drying" | "Rock is likely damp; friction will be reduced." |
| `wind_strong` | Wind > 20 mph | "Strong winds; exposed routes will be sketchy." |
| `temperature_extreme` | Temp < 30°F or > 90°F | "Cold temps reduce grip; hot temps increase fatigue." |
| `thunderstorm_high_probability` | Thunderstorm prob > 40% + high exposure | "Thunderstorm risk; avoid exposed routes." |
| `forecast_uncertain` | Forecast > 10 days out | "This forecast is speculative; plan flexibility." |
| `crowd_likely_weekend` | Weekend + high-crowd area | "Expect crowds; arrive early." |
| `approach_partially_affected` | Precip on approach route but not climb site | "Approach may be muddy; good shoes advised." |

---

## 5. Module Ownership & Refactoring Plan

### Current Files & Responsibilities

| File | Current Purpose | v1 Sendable Role | Status |
|------|-----------------|------------------|--------|
| `src/models.py` | Trip, Weather, Scores, Alert dataclasses | Extend with `ClimbingScores`, keep base models | Extend |
| `src/config.py` | PARKS dict + NPS API config | Replace with `CLIMBING_AREAS` dict | Refactor |
| `src/advisor.py` | High-level orchestration (deprecated in v1) | Remove (superseded by advisor_llm.py) | Remove |
| `src/advisor_llm.py` | LLM orchestration + prompt building | Core; adapt for climbing context | Refactor |
| `src/advisor_context.py` | Context builder (weather, alerts, RAG, trails) | Rename → `objective_context_builder.py`; adapt to climbing | Refactor |
| `src/scoring.py` | Hiking scoring logic | Port climbing weights; keep utility functions (temp, wind conversions) | Refactor |
| `src/prompt_builder.py` | Hiking prompt templates | Rewrite for climbing context | Refactor |
| `src/weather_client.py` | Open-Meteo integration | Use as-is | Reuse |
| `src/nps_client.py` | NPS alerts client | Replace with `climbing_alerts_client.py` (stubs in v1) | Replace |
| `src/rag/*.py` | RAG + embedding infrastructure | Use as-is; seed with climbing content | Reuse |
| `app.py` | CLI demo | Adapt to climbing workflow | Refactor |
| `ui_streamlit.py` | Streamlit UI | Major refactor: new form, new output display | Refactor |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/objectives/climbing_objective.py` | `ClimbingObjective`, `ClimbingRoute`, `RecommendedObjective` models |
| `src/adapters/base.py` | Abstract `ObjectiveAdapter` interface |
| `src/adapters/climbing_adapter.py` | `ClimbingAdapter` implementation (scoring, routing, prompt templates) |
| `src/climbing_alerts_client.py` | Climbing-specific alerts (stubs in v1; expand to web scrape in v1.1) |
| `data/climbing_seeds/` | Directory for RAG seed content (10–20 climbing articles) |
| `data/climbing_areas.yaml` or `src/climbing_areas_config.py` | v1 climbing area metadata (Red, Index, Bishop) |

---

## 6. Implementation Ownership & Entry Points

### Entry Point: `advise_objective()` (new top-level)

```python
# src/advisor_llm.py (or new src/sendable_advisor.py)

def advise_climbing_objective(objective: ClimbingObjective) -> SendableRecommendation:
    """
    Main entry point for v1. Orchestrates:
    1. Fetch weather for objective location
    2. Match user constraints to recommended crags/routes
    3. Score sendability
    4. Call LLM for explanation
    5. Return structured recommendation + plan
    """
    
    # 1. Fetch weather
    area = CLIMBING_AREAS[objective.area_id]
    weather_days = get_weather_for_trip(
        lat=area.lat,
        lon=area.lon,
        start_date=objective.start_date,
        end_date=objective.end_date,
    )
    
    # 2. Build context (weather, RAG, conditions)
    context = build_objective_context(objective, weather_days)
    
    # 3. Compute scores
    adapter = ClimbingAdapter(CLIMBING_AREAS)
    scores = adapter.compute_scores(objective, weather_days, context)
    
    # 4. Select primary & backup objectives
    primary, backup = adapter.select_objectives(
        objective, scores, context
    )
    
    # 5. Build LLM prompt
    prompt = build_climbing_advice_prompt(
        objective, scores, context, primary, backup
    )
    
    # 6. Call LLM
    explanation = _call_llm_with_prompt(prompt, system_message=CLIMBING_SYSTEM_MESSAGE)
    
    # 7. Extract verdict from explanation + scores
    verdict = _parse_sendability_verdict(explanation, scores)
    
    # 8. Build itineraries
    primary_plan = _build_day_plan(primary, objective, context)
    backup_plan = _build_day_plan(backup, objective, context)
    
    # 9. Return structured output
    return SendableRecommendation(
        sendability_verdict=verdict,
        sendability_score=scores.sendability_score,
        primary_objective=primary,
        backup_objective=backup,
        conditions_summary=context["conditions"],
        sendability_scores=scores,
        primary_plan=primary_plan,
        backup_plan=backup_plan,
        short_explanation=explanation[:200],
        detailed_explanation=explanation,
    )
```

---

## 7. v1 Scope Boundaries

### ✓ In Scope

- Single climbing objective per session (not multi-day trip planning)
- 3 hardcoded climbing areas (Red River Gorge, Index, Bishop)
- Sport, Trad, Boulder as climb types (no mixed rope systems)
- 16-day weather forecast window
- Local RAG over 10–20 climbing articles
- LLM-based sendability reasoning
- Simple day-plan output
- Streamlit UI with form + verdict display

### ✗ Out of Scope (v1.1+)

- Multi-day backcountry trips
- Real-time rock condition crowdsourcing
- Mountain Project API integration
- Ski objective support
- Partner matching
- Route finding / navigation
- Detailed topos / beta overlays
- User accounts / trip history

---

## 8. Data Flow Diagram

```
┌──────────────────────────────┐
│   USER FORM                  │
│ - Area: RRG                  │
│ - Grade: 5.10                │
│ - Type: Sport                │
│ - Dates: Apr 19-21           │
│ - Approach: <2hr             │
└──────────┬───────────────────┘
           │
           ▼
┌──────────────────────────────┐
│ ClimbingObjective dataclass  │
└──────────┬───────────────────┘
           │
           ├──────────────────────────────────┐
           │                                  │
           ▼                                  ▼
┌──────────────────────┐    ┌─────────────────────────┐
│ Weather Client       │    │ RAG Retriever           │
│ (Open-Meteo)        │    │ (Climbing articles)     │
│ → WeatherDay list   │    │ → DocumentChunk list    │
└──────────┬───────────┘    └──────────┬──────────────┘
           │                           │
           └──────────────┬────────────┘
                          │
                          ▼
          ┌──────────────────────────────────┐
          │ Objective Context Builder        │
          │ (assembles signals)              │
          │ → conditions, alert flags, etc.  │
          └──────────┬───────────────────────┘
                     │
                     ▼
          ┌──────────────────────────────────┐
          │ ClimbingAdapter.compute_scores() │
          │ (grade, rock, weather, exposure) │
          │ → ClimbingScores                 │
          └──────────┬───────────────────────┘
                     │
                     ├─────────────────────────────────┐
                     │                                 │
                     ▼                                 ▼
          ┌────────────────────────┐   ┌──────────────────────┐
          │ Select Objectives      │   │ Build LLM Prompt     │
          │ (match constraints)    │   │ (scores + context)   │
          │ → primary, backup      │   │ → prompt string      │
          └────────────────────────┘   └──────────┬───────────┘
                     │                           │
                     └───────────────┬───────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │ LLM Call (GPT-4)    │
                          │ → explanation       │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │ SendableRecommendation   │
                          │ - verdict                │
                          │ - objectives             │
                          │ - plans                  │
                          │ - explanation            │
                          └──────────┬───────────────┘
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │ Streamlit UI Display     │
                          │ (verdict, scores,        │
                          │  plans, reasoning)       │
                          └──────────────────────────┘
```

---

## 9. Quick Data Model Reference

For rapid implementation, here are the minimal required dataclasses:

```python
# src/models.py (existing, extend)
@dataclass
class ClimbingScores:
    grade_alignment: float
    rock_condition_score: float
    weather_score: float
    exposure_risk: float
    approach_feasibility: float
    sendability_score: float
    risk_flags: List[str]
    notes: List[str]

# src/objectives/climbing_objective.py (new)
@dataclass
class ClimbingObjective:
    area_id: str
    grade_min: str
    grade_max: str
    climb_type: str
    start_date: str
    end_date: str
    approach_time_tolerance_max: int
    commitment_level: str

@dataclass
class RecommendedObjective:
    ranking: int
    area_id: str
    area_name: str
    route_names: List[str]
    grades: List[str]
    climb_type: str
    avg_approach_minutes: float

@dataclass
class SendableRecommendation:
    sendability_verdict: str        # "GO", "CAUTION", "NO-GO"
    sendability_score: float
    primary_objective: RecommendedObjective
    backup_objective: RecommendedObjective
    conditions_summary: Dict[str, Any]  # temp, precip, wind, rock_condition, etc.
    sendability_scores: ClimbingScores
    primary_plan: Dict[str, Any]
    backup_plan: Dict[str, Any]
    short_explanation: str
    detailed_explanation: str

# src/config.py (refactor)
CLIMBING_AREAS = {
    "rrg": {
        "name": "Red River Gorge",
        "lat": 38.5,
        "lon": -83.7,
        "primary_rock_type": "sandstone",
        "typical_wetness_after_rain_hours": 24,
        "crowd_tendency": "high",
    },
    ...
}
```

---

## 10. Summary: What Changes, What Stays

| Component | v0 (Parks) | v1 (Sendable) | Migration Path |
|-----------|-----------|--------------|----------------|
| **Input** | Park + dates + hiker profile | Area + grade + dates + climb type | Form refactor |
| **Weather** | Open-Meteo (reuse) | Open-Meteo (reuse) | 0 changes |
| **Scoring** | 4 components (access, weather, crowd, risk) | 5 components (grade, rock, weather, exposure, approach) | Refactor weights |
| **Scoring backend** | `scoring.py` | Adapter pattern; climbing impl in adapter | Extend architecture |
| **RAG** | NPS articles | Climbing articles (seed 10–20) | Content swap; logic reuse |
| **Context** | Park-wide (trails, alerts) | Objective-specific (routes, beta) | Rename + adapt queries |
| **LLM** | Hiking advisor prompt | Climbing advisor prompt | Rewrite prompt template |
| **Output** | Trip readiness + recommendation | Sendability verdict + plans | New schema |
| **UI** | Park picker + trail display | Area picker + grade input + plan display | Full refactor |

---

