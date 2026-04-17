# Sendable: Product & Technical Transition Plan

**Date**: April 2026  
**From**: Parks Advisor (Yosemite-focused hiking advisor)  
**To**: Sendable (climbing-first decision-making agent, extensible to skiing)

---

## 1. Current-State Assessment

### Existing Strengths ✓

The Parks Advisor codebase has a solid, modular foundation that will serve Sendable well:

| Component | Status | Reusability |
|-----------|--------|------------|
| **Data Ingestion** | Working | HIGH |
| - Weather client (Open-Meteo) | Real-time forecasts via public API | Reuse as-is |
| - NPS alerts client | Park-level alerts & closures | Reuse, rename scope |
| - NPS articles & ThingsToDo RAG | Content ingestion pipeline | Adapt to climbing/skiing data sources |
| **Scoring Engine** | Foundational | HIGH |
| - Metric-to-imperial conversions | Handles weather, wind, temp conversions | Reuse |
| - Risk-flag system | Modular, extensible | Extend with domain-specific risks |
| - Composable weights | Access, weather, crowd signals | Adapt for climbing (exposure, grade, conditions) |
| **Orchestration** | Solid | HIGH |
| - Trip context builder | Assembles weather, alerts, scores, RAG, trails | Rename/refactor for "objective context" |
| - Advisor LLM layer | Prompt composition + OpenAI calls | Reuse architecture, refactor prompts |
| - RAG retriever (Chroma + SentenceTransformers) | Local vector DB, no API keys | Reuse for climbing guides, condition reports, trip reports |
| **UI Layer** | Streamlit-based | MEDIUM |
| - Park/date picker | Trip input form | Adapt to climbing objective input (crag, grade, season) |
| - Score badges & display | Visual risk communication | Reuse styling, adapt data fields |
| - Alert/context display | Dashboard layout | Reuse layout, adapt content |

| **UI stack assumption** | Streamlit-based | Preserve for now, but evaluate map-first UI later |

### Existing Gaps / Constraints ✗

| Issue | Impact | Solution |
|-------|--------|----------|
| **Hard-coded Yosemite data** | NPS content, trail cards, park codes everywhere | Extract configurable "content adapters"; implement climbing data source |
| **Hiking-centric scoring** | Weights assume day-hikes (temp, wind, crowds matter) | Create domain-agnostic scoring backbone + climbing scoring rules (grade, exposure, approach length, conditions) |
| **Trail-based planning** | Obsessed with "recommended trails" from NPS | Shift to objective-centric: given a crag/route, is it sendable given conditions? |
| **"Park" concept** | Model assumes a geographic park with lat/lon | Generalize to "objective" (a crag, a ski zone, a peak) |
| **Missing critical climbing data** | No real-time bolting status, beta, grade info | Must infer from RAG or external climbing DBs (MP, 8a.nu, Mountain Project API) |
| **No multi-day ski trip planning** | Only single-park, single-activity forecasts | Design for multi-day backcountry (avalanche forecasts, hut availability, etc.) |

---

## 2. Reuse vs Refactor vs Remove

### ✓ REUSE (No Changes)

- **Open-Meteo weather client** → Use for climbing objective forecasts
- **LLM orchestration** → Same pattern for climbing advisor (build context, compose prompt, call LLM)
- **Chroma + SentenceTransformers RAG** → Perfect for climbing condition reports, guides, community beta
- **Risk-flag architecture** → Extend with climbing-specific flags (poor_protection, wet_rock, thunderstorm_exposure)
- **Dataclass models** → Extend, don't rewrite

### 🔄 REFACTOR (Adapt Core Logic)

| Component | Current | Sendable Target | Effort |
|-----------|---------|-----------------|--------|
| **Trip/Objective model** | `TripRequest` (park + dates + activity) | `ObjectiveRequest` (crag + season + grade + approach) | S |
| **Scoring engine** | Hiking weights (access 35%, weather 45%, crowd 20%) | Climbing weights (route_grade 30%, conditions 35%, exposure 20%, traffic 15%) | M |
| **Scores dataclass** | access, weather, risk, crowd, readiness | grade_alignment, rock_condition, exposure_risk, approach_feasibility, sendability | S |
| **Context builder** | Park → trails + weather + alerts | Objective → conditions + approach weather + beta + similar climbs | M |
| **Prompt builder** | Hiking trip narrative | Climbing objective narrative + grade, protection, approach details | M |
| **Config** | PARKS dict (Yosemite) | CLIMBING_AREAS (Red, Index, Bishop) + adapter pattern for future hiking/skiing | M |

### ✗ REMOVE (Out of Scope)

- **NPS-specific trails (ArcGIS)** → Not relevant to climbing; replace with climbing DB lookups
- **NPS articles ingestion** → Replace with climbing blogs, condition reports, trip reports
- **"Things to Do" concepts** → Climbing doesn't use this model; focus on route/crag descriptions
- **Crowd/seasonality scoring** → Not removed, but de-prioritized for v1
- **Park-level geographic unit** → Replaced by crag/objective model

---

## 3. Target Product Definition

### Mission
**Sendable answers: "Is this actually sendable?"**

Given a climbing objective (crag + routes + season), Sendable assesses real-time/forecast conditions and outputs a decision:
- **SEND IT** – conditions are favorable
- **APPROACH WITH CAUTION** – doable, but watch for specific hazards
- **NOT TODAY** – conditions aren't right

### User Workflow (v1)
1. User selects or describes a climbing objective (e.g., "Red River Gorge, 5.11 sport climbing, next weekend")
2. App ingests current/forecast weather, rock conditions, approach conditions
3. App retrieves relevant beta from community sources (MP, guides, trip reports)
4. Scoring engine ranks sendability against grade, exposure, condition risks
5. LLM advisor produces a decision + reasoning (weather window? wet rock? crowd?)
6. UI shows: verdict, risk breakdown, suggested conditions/timing, gear tips

### Non-Goals (v1)
- Route finding / navigation
- Detailed topo drawings
- Real-time peer crowd counts
- Multi-pitch rope rescue training
- Partner matching
- Accommodation booking

### Core UX Principle
The product should be able to render objective recommendations on a map as a first-class experience. The current UI can remain Streamlit-based for v1, but all outputs should include location coordinates, area metadata, and optional route geometry so a future map-first interface can be built cleanly.

---

## 4. V1 Scope (MVP)

### Must-Have (Week 1–2)
- [ ] Refactor `TripRequest` → `ClimbingObjective` (crag, route_grade, season)
- [ ] Refactor scoring: climbing-centric weights
- [ ] Swap NPS articles → climbing blog/report RAG (seed with 5–10 key climbing articles)
- [ ] LLM prompt: climbing-specific system message + context
- [ ] Streamlit UI: crag selector (hardcoded: Red, Index, Bishop) + grade input + date range
- [ ] Weather + conditions display (same format, climbing-relevant fields)
- [ ] Sendability verdict (GO / CAUTION / AVOID)

### Nice-to-Have (Week 3+)
- [ ] Integrate Mountain Project API (read-only) for real route data
- [ ] Avalanche forecasts for ski objectives
- [ ] Multi-day backcountry trip scaffolding
- [ ] Community trip report RAG enrichment
- [ ] Rock condition signals (wet, slick, frozen)

### Out-of-Scope (v1)
- Weather-based partner matching
- Route-by-route protection quality scoring
- Real-time community feedback
- Ski-specific planning (defer to v1.5)

---

## 5. Architecture Proposal

### High-Level Flow

```
┌────────────────────────────────────────────────────────────┐
│                    USER INPUT                              │
│  (Crag selection, grade, season, dates)                    │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│         OBJECTIVE CONTEXT BUILDER                           │
│  (Orchestrator: assembles all signals)                     │
├────────────────────────────────────────────────────────────┤
│ ├─ Weather Client (Open-Meteo)                            │
│ │  → forecast for crag location + dates                   │
│ ├─ Conditions Client (TBD: MP API / web scrape)          │
│ │  → route grades, protection, recent ascents             │
│ ├─ Alert Client (NPS / local gov't)                       │
│ │  → road closures, fire zones, permit reqs               │
│ ├─ RAG Retriever (Chroma)                                 │
│ │  → climbing blogs, trip reports, condition beta         │
│ └─ Domain Adapter (climbing-specific scoring)             │
│    → grade alignment, rock condition, exposure risk       │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│           SCORING ENGINE (domain-agnostic backbone)        │
├────────────────────────────────────────────────────────────┤
│ ├─ Metric collection (weather, alerts, context signals)  │
│ ├─ Climbing-specific risk flags:                          │
│ │  - exposure_risk, wet_rock, thunderstorm, grade_mismatch│
│ ├─ Weighted scoring (route_grade 30%, conditions 35%, ...) │
│ └─ Output: Scores + risk_flags + notes                    │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│              LLM ADVISOR (prompt + call)                    │
├────────────────────────────────────────────────────────────┤
│ ├─ System: "You are a cautious climbing advisor..."      │
│ ├─ Prompt: Scores + weather + alerts + RAG context       │
│ ├─ Call: OpenAI GPT-4 (or selected model)                │
│ └─ Output: Verdict (SEND / CAUTION / AVOID) + reasoning  │
└────────────────┬─────────────────────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────────────┐
│                 OUTPUT / UI LAYER                          │
│  (Streamlit dashboard → Verdict + risk breakdown)         │
└────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Domain Adapters (Extensibility)
Instead of hard-coding climbing logic, create a "domain adapter" abstraction:

```
src/
├── adapters/
│   ├── __init__.py
│   ├── base.py              # Abstract adapter interface
│   ├── climbing.py          # Climbing-specific implementation
│   └── skiing.py            # (Future) Ski-specific implementation
│
├── objectives/
│   ├── __init__.py
│   ├── climbing_objective.py  # ClimbingObjective model
│   └── ski_objective.py       # (Future) SkiObjective model
```

Each adapter implements:
- **Data sources**: Which APIs/RAG sources to use
- **Scoring rules**: Weights, thresholds, risk flags
- **Prompt templates**: LLM system message + context formatting
- **Output interpretation**: How to present verdict + reasoning

#### 2. Scoring as a Composable Pipeline
Refactor `src/scoring.py` to support pluggable domain scorers:

```python
# Current: hiking-specific scoring
scores = compute_scores(trip, weather_days, alerts)

# New: adapter-aware scoring
adapter = get_adapter(objective.domain)  # "climbing" or "skiing"
scores = adapter.compute_scores(objective, weather_days, alerts, context)
```

#### 3. Models Hierarchy
Keep `src/models.py` as the base; create domain-specific submodules:

```python
# src/models.py (unchanged, foundation)
@dataclass
class Scores:
    ...

# src/objectives/climbing_objective.py (new)
@dataclass
class ClimbingObjective:
    crag_name: str
    route_grade: str  # "5.10a", "V5", etc.
    approach_minutes: Optional[int]
    exposure_level: str  # "low", "moderate", "high"
    season: str  # "spring", "summer", "fall", "winter"
    dates: Tuple[date, date]

@dataclass
class ClimbingScores(Scores):
    grade_alignment: float  # How well grade matches climber skill / conditions
    rock_condition: float   # Wetness, temperature, brittleness
    exposure_risk: float    # Thunderstorm, rockfall, commitment level
    approach_feasibility: float
    sendability_score: float  # Overall "is it sendable?"
```

#### 4. RAG Content Sources
Evolve from NPS articles → climbing-specific sources:

| Source | Type | Ingestion |
|--------|------|-----------|
| Mountain Project (public data) | Route guides, topos | API (read-only) or web scrape |
| 8a.nu (public data) | Community route info | Web scrape (with permission) |
| Local condition reports | Community blogs, subreddits | Manual curation + web scrape |
| Weather-climbing correlations | Climbing blogs, magazines | Manual curation |
| Trip reports (public) | Community experiences | Web scrape (8a, MP, subreddits) |

Start v1 with 10–20 manually curated climbing articles (Red River Gorge, granite climbing in winter, etc.) to seed RAG. Expand in v1.5.

#### 5. Config Refactor
```python
# src/config.py (current: PARKS dict)

# New structure:
CLIMBING_AREAS = {
    "red_river_gorge": {
        "name": "Red River Gorge, KY",
        "lat": 38.5, "lon": -83.7,
        "primary_grades": ["5.9", "5.10", "5.11"],
        "seasons": ["spring", "fall"],
        "notable_routes": [...],
        "access_info": "...",
    },
    ...
}

# Factory function:
def get_adapter(domain: str) -> ObjectiveAdapter:
    if domain == "climbing":
        return ClimbingAdapter(CLIMBING_AREAS)
    elif domain == "skiing":
        return SkiingAdapter(SKI_ZONES)
    else:
        raise ValueError(...)
```

---

## 6. Phased Implementation Plan

### Phase 0: Planning & Scaffolding (1 day)
- [x] Write this plan
- [ ] Create branch: `feat/sendable-mvp`
- [ ] Scaffold `src/adapters/` and `src/objectives/` directories
- [ ] Define abstract `ObjectiveAdapter` base class

### Phase 1: Core Refactor (3–4 days)
- [ ] Create `ClimbingObjective` model (refactor from `TripRequest`)
- [ ] Create `ClimbingScores` model (refactor from `Scores`)
- [ ] Implement `ClimbingAdapter` with climbing-specific scoring weights
- [ ] Refactor `advisor_context.py` → generic context builder that accepts adapters
- [ ] Update `scoring.py` to support pluggable domain logic
- [ ] Create minimal climbing RAG seed (10 articles in `data/climbing_seeds/`)

### Phase 2: LLM & Prompts (2 days)
- [ ] Rewrite `prompt_builder.py` for climbing context
- [ ] Update system message in `advisor_llm.py` for climbing advisor
- [ ] Test prompt quality with 2–3 manual examples
- [ ] Refactor verdict parsing (SEND / CAUTION / AVOID instead of GO / CAUTION / AVOID)

### Phase 3: UI Adaptation (2 days)
- [ ] Update `ui_streamlit.py`:
  - Crag selector (hardcoded: Red, Index, Bishop)
  - Grade input (5.9–5.15 scale)
  - Season selector
  - Display climbing-relevant scores
  - Show sendability verdict prominently
- [ ] Adapt score badges for climbing language
- [ ] Add "Why this verdict?" expandable section (LLM reasoning)

### Phase 4: Testing & Polish (1 day)
- [ ] Manual end-to-end test with 3–5 realistic climbing scenarios
- [ ] Validate scoring logic (does high wind = caution? does summer heat = caution?)
- [ ] Check RAG relevance (does "wet rock" query return useful results?)
- [ ] UI Polish (fonts, colors, layout)

### Phase 5: v1 Release & Docs (1 day)
- [ ] Update README.md (rename, add climbing focus)
- [ ] Write quick-start guide for climbing use case
- [ ] Tag v1.0

**Timeline**: ~10 days elapsed, ~40 hours engineering effort

---

## 7. Risks & Open Questions

### Technical Risks

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| **LLM hallucination on grades** | High | Anchor LLM prompts with real route data; require explicit numeric grade in context |
| **Weather API doesn't cover all crags** | Medium | Open-Meteo covers globe at 0.1° granularity; should be fine for US crags. Test edge cases (Mt. Rainier). |
| **Climbing RAG seed is too small** | High | v1 ships with 10 articles; v1.1 expands to 50+. Monitor relevance in early usage. |
| **Grade mismatch scoring is subjective** | High | Define clear rules: 5.10a attempt by 5.9 climber = mismatch flag. Validate with users. |
| **Exposure risk is hard to quantify** | High | Lean on LLM to interpret; risk flags guide (thunderstorm + 5.11 exposed = caution). |

### Product / Domain Risks

| Risk | Likelihood | Mitigation |
|------|------------|-----------|
| **Real climbers won't trust an app's "sendable" verdict** | High | Be conservative in v1. Always say "ask your partners" + "use your judgment." Iterate on prompt based on feedback. |
| **Conditions change hourly; forecast outdated by publish** | Medium | Set user expectations: "This is a planning aid, not a real-time spotter." Consider hourly updates in v1.1. |
| **Missing critical data (bolting status, rockfall history)** | High | For v1, rely on RAG + LLM to surface recent reports. In v1.1, integrate MP API for real route data. |
| **Scope creep to skiing / multi-sport** | High | Keep `src/adapters/` pattern strict. Skiing scaffolded but not implemented in v1. Reject non-climbing feature requests. |

### Open Questions

1. **How to source climbing condition reports in bulk?**
   - Scrape 8a.nu? Partner with MP? Manual curation + user feedback loop?
   - → v1: Manual curation. v1.1: Lightweight scraper.

2. **Should we show grade-specific recommendations?**
   - E.g., "Try 5.10d instead of 5.11a because of wind"?
   - → v1: No. Just pass/fail on the selected grade.

3. **How many climbing areas in v1?**
   - Red River Gorge, Index, Bishop only (3)?
   - → YES. Depth over breadth. Nail the experience for one area.

4. **Real-time rock condition data?**
   - APIs? User reports? Machine learning on weather → rock?
   - → v1: Inferred from weather (rain → wet, cold → hard). Expand in v1.1.

5. **Multi-pitch vs. single-pitch scoring?**
   - Different risk profiles (commitment, retreat complexity).
   - → v1: Treat uniformly. v1.1: Add multi-pitch mode.

---

## 8. Recommended Next Coding Steps

### Immediate (This Week)

1. **Create `src/adapters/base.py`**
   - Define `ObjectiveAdapter` abstract class with methods:
     ```python
     class ObjectiveAdapter:
         def compute_scores(self, objective, weather, alerts, context) -> Scores
         def format_for_prompt(self, context) -> str
         def get_data_sources(self, objective) -> List[DataSource]
     ```

2. **Create `src/objectives/climbing_objective.py`**
   - Move climbing-specific models here
   - Define `ClimbingObjective` and `ClimbingScores` dataclasses
   - Document required fields (grade, exposure, season)

3. **Create `src/adapters/climbing.py`**
   - Implement `ClimbingAdapter` with climbing-specific scoring
   - Port & adapt weights from `src/scoring.py`
   - Define climbing risk flags: `exposure_risk`, `wet_rock`, `grade_mismatch`, `thunderstorm_exposure`, etc.

4. **Refactor `src/advisor_context.py`**
   - Make it accept an `ObjectiveAdapter` as a parameter
   - Replace `park_code` lookups with `objective.crag_name`
   - Update RAG queries to be climbing-focused (e.g., "5.10 climbing at Red River Gorge")

5. **Create `data/climbing_seeds/`**
   - Add 5–10 climbing articles (PDFs or markdown files with metadata)
   - Source: climbing magazines (Rock and Ice, Climbing), blogs (climbing-themed subreddits), community posts
   - Ensure each has: title, author, date, grade range, crag, key topics

### Parallel (This Week)

6. **Update `ui_streamlit.py` (sketch)**
   - Add conditional UI paths: `if domain == "climbing"` vs `if domain == "hiking"`
   - Add crag selector (start with hardcoded 3: Red, Index, Bishop)
   - Add grade input (dropdown: 5.9 → 5.15)
   - Remove park selector (locked to climbing in v1)

7. **Update `requirements.txt`**
   - Add dependencies if needed (none immediately; current stack is sufficient)

### Week 2

8. **Integrate RAG with climbing articles**
   - Test that climbing article ingestion works
   - Run sample queries: "5.10 climbing Red River Gorge" → verify results

9. **Rewrite `prompt_builder.py` for climbing**
   - New system message: "You are a cautious, experienced climbing advisor..."
   - New context format: crag, grade, weather, risk flags, recent beta
   - Test with manual examples

10. **End-to-end test (1–2 realistic scenarios)**
    - User selects: Red River Gorge, 5.10a, next weekend
    - System returns: weather, scores, LLM verdict
    - Manually verify reasoning makes sense

---

## Summary

**Sendable is a product pivot, not a rebuild.**

Reuse the solid orchestration, scoring, and LLM architecture from Parks Advisor. Extract climbing logic into adapters so skiing (and other outdoor objectives) can be added later. Start narrow (Red River Gorge, simple grades, basic weather/conditions). Let early user feedback and data inform the next phases.

The existing codebase is 80% there. The work is mostly in **renaming concepts** (park → objective, hike → route) and **adapting scoring logic** (temp/wind comfort → grade/exposure fit), not rewriting from scratch.

