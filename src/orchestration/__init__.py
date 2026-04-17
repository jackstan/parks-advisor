"""
Orchestration layer: domain-agnostic planner and orchestrator.

The orchestrator ties together:
- Domain models
- Weather integration
- Alerts integration
- Scoring
- RAG
- LLM advisor
- Domain adapters
"""

# Import main planner entry point
from .planner import (
    generate_candidates,
    evaluate_candidates,
    rank_candidates,
    select_primary_and_backup,
    generate_plan,
    assemble_recommendation,
    plan_outdoor_objective,
)

# Keep old functions for backward compatibility
from typing import Dict, List, Any
from ..domain.objective_models import Objective, ObjectiveRecommendation
from ..models import WeatherDay
from ..integrations.weather import get_weather_for_location
from ..adapters import get_adapter


def build_objective_context(
    objective: Objective,
    location_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a rich context dict for an objective.
    
    This orchestrates:
    1. Fetch weather data
    2. Fetch alerts
    3. Retrieve RAG content
    4. Build conditions summary
    
    Returns:
        Context dict suitable for passing to adapter.compute_scores()
    """
    adapter = get_adapter(objective.domain)

    # 1. Weather
    lat = location_metadata.get("lat")
    lon = location_metadata.get("lon")
    if lat is None or lon is None:
        raise ValueError("location_metadata must include 'lat' and 'lon'")
    
    weather_days = get_weather_for_location(
        lat=float(lat),
        lon=float(lon),
        start_date=objective.start_date,
        end_date=objective.end_date,
        location_id=objective.location_id,
    )
    
    # 2. Alerts
    alerts = []
    alert_provider = adapter.get_alert_provider(objective)
    if alert_provider is not None:
        alerts = alert_provider.get_alerts(objective.location_id)
    
    # 3. RAG content (stub for now; will be populated by RAG layer)
    rag_chunks = []
    
    return {
        "objective": objective,
        "weather": weather_days,
        "alerts": alerts,
        "rag_chunks": rag_chunks,
        "location_metadata": location_metadata,
        "content_providers": adapter.get_content_providers(objective),
    }


def evaluate_objective(
    objective: Objective,
    location_metadata: Dict[str, Any],
) -> ObjectiveRecommendation:
    """
    Evaluate an objective end-to-end.
    
    Orchestrates:
    1. Build objective context
    2. Get domain adapter
    3. Compute scores
    4. Format for LLM
    5. Call LLM
    6. Parse verdict
    7. Return recommendation
    
    Args:
        objective: The objective to evaluate
        location_metadata: Metadata about the location (lat, lon, etc.)
    
    Returns:
        ObjectiveRecommendation with verdict, scores, and explanation
    """
    # 1. Build context
    context = build_objective_context(objective, location_metadata)
    weather_days = context.get("weather", [])
    
    # 2. Get domain adapter
    adapter = get_adapter(objective.domain)
    
    # 3. Compute scores
    scores = adapter.compute_scores(objective, weather_days, context)
    
    # 4. Format context for LLM
    llm_context = adapter.format_context_for_llm(objective, scores, context)
    
    # 5. Call LLM (stub for now; placeholder explanation)
    from ..advisor_llm import _call_llm_with_prompt
    system_message = adapter.get_system_message()
    prompt = f"{system_message}\n\n{llm_context}"
    llm_output = _call_llm_with_prompt(prompt)
    
    # 6. Parse verdict
    verdict = adapter.parse_verdict(llm_output, scores)
    
    # 7. Build recommendation
    return ObjectiveRecommendation(
        objective=objective,
        verdict=verdict,
        overall_score=scores.trip_readiness_score,
        component_scores={
            "access": scores.access_score,
            "weather": scores.weather_score,
            "crowd": scores.crowd_score,
            "risk": scores.risk_score,
        },
        risk_flags=scores.risk_flags,
        short_explanation=f"{verdict}: {scores.notes[0] if scores.notes else 'See details below.'}",
        detailed_explanation=llm_output,
        conditions_at_location=context,
    )


__all__ = [
    # New planner functions
    "generate_candidates",
    "evaluate_candidates",
    "rank_candidates",
    "select_primary_and_backup",
    "generate_plan",
    "assemble_recommendation",
    "plan_outdoor_objective",
    # Old functions (for backward compat)
    "build_objective_context",
    "evaluate_objective",
]
