from typing import Tuple

from .models import TripRequest, Scores
from .advisor_context import build_trip_context
from .prompt_builder import build_trip_advice_prompt


def advise_trip_with_explanation(trip: TripRequest) -> Tuple[Scores, str, str]:
    """
    High-level advisor:
    - builds full data + RAG context
    - builds an LLM-ready prompt
    - returns:
        scores          -> numeric model output
        explanation     -> placeholder explanation (LLM will replace later)
        prompt_debug    -> the full prompt we'd send to the LLM
    """
    context = build_trip_context(trip)
    scores: Scores = context["scores"]

    prompt = build_trip_advice_prompt(context)

    # Simple rule-based verdict for now (stub instead of a real LLM call)
    if scores.trip_readiness_score >= 80 and "access_risk" not in scores.risk_flags:
        verdict = "GO"
    elif scores.trip_readiness_score >= 60:
        verdict = "GO-WITH-CAUTION"
    else:
        verdict = "AVOID"

    explanation = (
        f"Verdict: {verdict}\n"
        f"- Trip readiness: {scores.trip_readiness_score:.0f}/100\n"
        f"- Access score: {scores.access_score:.0f}/100\n"
        f"- Weather score: {scores.weather_score:.0f}/100\n"
        f"- Risk flags: {', '.join(scores.risk_flags) if scores.risk_flags else 'none'}\n\n"
        "This explanation is currently rule-based. In a later step, this function will call "
        "a real LLM with `prompt_debug` to generate a richer, grounded narrative using the "
        "scores, alerts, and official snippets."
    )

    return scores, explanation, prompt
