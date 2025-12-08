# src/advisor_llm.py

from typing import Tuple
from . import config  # noqa: F401  # ensures .env is loaded via config.py

from openai import OpenAI

from .models import TripRequest, Scores
from .advisor_context import build_trip_context
from .prompt_builder import build_trip_advice_prompt

client = OpenAI()


def _call_llm_with_prompt(prompt: str) -> str:
    """
    Call the OpenAI chat model with the full prompt text.
    If anything goes wrong, return a clear fallback message.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cautious, realistic, safety-focused Yosemite "
                        "trip-planning assistant. You give practical, conservative "
                        "advice and never overstate safety."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        # Fallback so the rest of the app doesn't crash if the LLM call fails
        return (
            "The trip advisor's language model call failed. "
            "Here is a placeholder explanation instead. "
            f"(Internal error: {e})"
        )


def advise_trip_with_explanation(trip: TripRequest) -> Tuple[Scores, str, str]:
    """
    High-level advisor function.

    Orchestrates:
      - build_trip_context(trip)       -> gathers weather, alerts, scores, RAG
      - build_trip_advice_prompt(...)  -> builds a detailed LLM prompt
      - _call_llm_with_prompt(...)     -> gets a natural-language explanation

    Returns:
      scores: Scores       - numeric summary (access, weather, readiness, etc.)
      explanation: str     - narrative advice from the LLM
      prompt_debug: str    - the exact prompt sent to the LLM (for debugging)
    """

    # 1) Build trip context dict
    context = build_trip_context(trip)

    # 2) Build the LLM-ready prompt string (includes trip, scores, weather, alerts, RAG)
    prompt = build_trip_advice_prompt(context)

    # 3) Call the LLM to generate an explanation
    explanation = _call_llm_with_prompt(prompt)

    # 4) Extract the scores out of the context for convenient return
    scores: Scores = context["scores"]

    return scores, explanation, prompt
