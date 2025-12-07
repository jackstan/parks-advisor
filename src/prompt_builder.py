from typing import Dict, Any, List

from .models import TripRequest, Scores, Alert, DocumentChunk


def build_trip_advice_prompt(context: Dict[str, Any]) -> str:
    trip: TripRequest = context["trip"]
    scores: Scores = context["scores"]
    alerts: List[Alert] = context["alerts"]
    chunks: List[DocumentChunk] = context["rag_chunks"]

    # 1) System / role + basic trip info
    header = (
        "You are an experienced Yosemite trip-planning assistant. "
        "Use the structured data and official information below to give realistic, "
        "risk-aware advice.\n\n"
        f"Trip details:\n"
        f"- Park: {trip.park_code}\n"
        f"- Dates: {trip.start_date} to {trip.end_date}\n"
        f"- Activity: {trip.activity_type}\n"
        f"- Hiker profile: {trip.hiker_profile}\n"
        f"- Constraints: {trip.constraints}\n\n"
    )

    # 2) Scores
    scores_text = (
        "Trip scores:\n"
        f"- Access score: {scores.access_score:.0f}/100\n"
        f"- Weather score: {scores.weather_score:.0f}/100\n"
        f"- Trip readiness: {scores.trip_readiness_score:.0f}/100\n"
        f"- Risk flags: {', '.join(scores.risk_flags) if scores.risk_flags else 'none'}\n"
    )

    if scores.notes:
        scores_text += "Score notes:\n" + "\n".join(f"- {n}" for n in scores.notes) + "\n"

    # 3) Alerts
    if alerts:
        alerts_text = "Current NPS alerts:\n"
        for a in alerts[:5]:
            alerts_text += f"- [{a.category}] {a.title}\n"
            if a.summary:
                summary_clean = a.summary[:200].replace("\n", " ")
                alerts_text += f"  {summary_clean}...\n"
    else:
        alerts_text = "Current NPS alerts: none returned.\n"


    # 4) RAG snippets
    if chunks:
        rag_text = "Relevant official information snippets:\n"
        for i, c in enumerate(chunks[:5]):
            rag_text += f"[Snippet {i+1}] Source: {c.source or 'NPS article'}\n"
            rag_text += c.text[:400].replace("\n", " ") + "\n\n"
    else:
        rag_text = "No additional official documentation snippets retrieved.\n"

    # 5) Instructions to the LLM
    instructions = (
        "Using ONLY the information above, answer the following:\n"
        "1) Give a verdict: GO, GO-WITH-CAUTION, or AVOID.\n"
        "2) Explain your verdict in 2–4 short paragraphs.\n"
        "3) Call out specific risks (weather, access, seasonality) and how to mitigate them.\n"
        "4) Suggest high-level trail or activity types suitable for this trip, "
        "given the conditions (not specific trails by name).\n"
        "5) List 3–6 concrete safety or gear recommendations.\n"
        "6) If information is missing or uncertain, say so explicitly.\n"
    )

    return header + scores_text + "\n" + alerts_text + "\n" + rag_text + "\n" + instructions
