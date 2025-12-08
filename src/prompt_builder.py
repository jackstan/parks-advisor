from typing import Dict, Any, List

from .models import TripRequest, Scores, Alert, DocumentChunk, WeatherDay


# --- Unit conversions ---------------------------------------------------------

def c_to_f(c: float) -> float:
    return (c * 9/5) + 32

def mps_to_mph(mps: float) -> float:
    return mps * 2.23694


# --- Weather formatting -------------------------------------------------------

def _format_weather_section(weather: List[WeatherDay]) -> str:
    if not weather:
        return "Weather forecast: no data returned.\n"

    text = "Weather forecast (°F, mph):\n"
    for day in weather[:7]:  # limit to a week for readability
        high_f = c_to_f(day.temp_max_c)
        low_f  = c_to_f(day.temp_min_c)
        wind_mph = mps_to_mph(day.wind_speed_max_mps)
        precip_prob = day.precip_probability * 100

        line = (
            f"- {day.date}: high {high_f:.0f}°F / low {low_f:.0f}°F, "
            f"precip {day.precip_mm:.1f} mm (~{precip_prob:.0f}%), "
            f"wind max {wind_mph:.0f} mph, "
            f"heat risk: {day.heat_index_risk}, "
            f"storm risk: {day.storm_risk}"
        )
        text += line + "\n"

    return text + "\n"


# --- Main prompt builder ------------------------------------------------------

def build_trip_advice_prompt(context: Dict[str, Any]) -> str:
    trip: TripRequest = context["trip"]
    scores: Scores = context["scores"]
    alerts: List[Alert] = context["alerts"]
    chunks: List[DocumentChunk] = context["rag_chunks"]
    weather: List[WeatherDay] = context["weather"]   # <<< NEW

    # 1) Header
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
    f"- Crowd score: {scores.crowd_score:.0f}/100\n"
    f"- Trip readiness: {scores.trip_readiness_score:.0f}/100\n"
    f"- Risk flags: {', '.join(scores.risk_flags) if scores.risk_flags else 'none'}\n"
    )


    if scores.notes:
        scores_text += "Score notes:\n" + "\n".join(f"- {n}" for n in scores.notes) + "\n"

    # 3) Weather (NEW SECTION)
    weather_text = _format_weather_section(weather)

    # 4) Alerts
    if alerts:
        alerts_text = "Current NPS alerts:\n"
        for a in alerts[:5]:
            alerts_text += f"- [{a.category}] {a.title}\n"
            if a.summary:
                summary_clean = a.summary[:200].replace("\n", " ")
                alerts_text += f"  {summary_clean}...\n"
    else:
        alerts_text = "Current NPS alerts: none returned.\n"

    # 5) RAG Snippets
    if chunks:
        rag_text = "Relevant official information snippets:\n"
        for i, c in enumerate(chunks[:5]):
            rag_text += f"[Snippet {i+1}] Source: {c.source or 'NPS article'}\n"
            rag_text += c.text[:400].replace("\n", " ") + "\n\n"
    else:
        rag_text = "No additional official documentation snippets retrieved.\n"

    # 6) Instructions for the LLM
    instructions = (
        "Using ONLY the information above, answer the following:\n"
        "1) Give a verdict: GO, GO-WITH-CAUTION, or AVOID.\n"
        "2) Explain your verdict in 2–4 short paragraphs.\n"
        "3) Call out specific risks (weather, access, seasonality) and how to mitigate them.\n"
        "4) Suggest 2–4 specific trail options BY NAME **only if** they are mentioned "
        "or clearly implied in the snippets above. For each suggested trail, briefly note:\n"
        "   - who it is suitable for (based on the hiker profile and conditions), and\n"
        "   - why you chose it.\n"
        "   When you recommend a trail, reference the snippet number(s) that support it, e.g. "
        "\"(from Snippet 2)\". If the snippets do not mention any specific trails, stay at "
        "the level of trail TYPES (e.g. \"moderate valley-floor loops\") instead of naming trails.\n"
        "5) List 3–6 concrete safety or gear recommendations.\n"
        "6) If the data above explicitly indicates missing or uncertain information "
        "(for example notes mentioning 'weather_uncertain' or missing forecasts), "
        "say so clearly. Otherwise, do not describe the forecast as 'far in advance', "
        "but you may still note that short-term forecasts can change.\n"
    )


    # Combine all sections
    return (
        header
        + scores_text + "\n"
        + weather_text + "\n"
        + alerts_text + "\n"
        + rag_text + "\n"
        + instructions
    )
