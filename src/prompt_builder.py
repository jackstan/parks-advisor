from typing import Dict, Any, List

from .models import TripRequest, Scores, Alert, DocumentChunk, WeatherDay


# --- Unit conversions ---------------------------------------------------------

def c_to_f(c: float) -> float:
    return (c * 9 / 5) + 32


def mps_to_mph(mps: float) -> float:
    return mps * 2.23694


# --- Weather formatting -------------------------------------------------------

def _format_weather_section(weather: List[WeatherDay]) -> str:
    if not weather:
        return "Weather forecast: no data returned.\n"

    text = "Weather forecast (°F, mph):\n"
    for day in weather[:7]:
        high_f = c_to_f(day.temp_max_c)
        low_f = c_to_f(day.temp_min_c)
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


# --- Trails selection + formatting --------------------------------------------

def _effective_hike_miles_upper(t: Any) -> float:
    """
    Conservative-but-realistic upper bound used ONLY for selection (not UI).
    """
    rc = getattr(t, "route_class", "unknown")

    if rc == "loop":
        loop = getattr(t, "loop_miles", None)
        if isinstance(loop, (int, float)) and loop > 0:
            return float(loop)

    if rc == "out_and_back":
        ow = getattr(t, "one_way_miles", None)
        if isinstance(ow, (int, float)) and ow > 0:
            return 2.0 * float(ow)

    if rc == "network":
        span = getattr(t, "span_miles", None)
        if isinstance(span, (int, float)) and span > 0:
            # Don't double networks for selection; people choose canonical variants.
            return float(span)

    tot = getattr(t, "total_miles", None)
    if isinstance(tot, (int, float)) and tot > 0:
        return float(tot)

    return 0.0


def _has_multi_segment_structure(t: Any) -> bool:
    tot = getattr(t, "total_miles", None)
    span = getattr(t, "span_miles", None)
    ow = getattr(t, "one_way_miles", None)
    base = None
    for v in (span, ow):
        if isinstance(v, (int, float)) and v > 0:
            base = float(v)
            break
    return (
        isinstance(tot, (int, float))
        and base is not None
        and float(tot) > base * 1.5
    )


def _select_trails_for_prompt(trails: List[Any], constraints: Dict[str, Any], limit: int = 12) -> List[Any]:
    if not trails:
        return []

    max_hours = None
    if isinstance(constraints, dict):
        max_hours = constraints.get("max_hike_hours")

    pace_mph = 2.0  # selection only
    max_miles = (max_hours * pace_mph) if isinstance(max_hours, (int, float)) else None

    with_signal = [t for t in trails if _effective_hike_miles_upper(t) > 0]
    if not with_signal:
        return trails[:limit]

    if max_miles is None:
        with_signal.sort(key=_effective_hike_miles_upper)
        step = max(1, len(with_signal) // limit)
        return with_signal[::step][:limit]

    candidates = [t for t in with_signal if _effective_hike_miles_upper(t) <= max_miles]

    if len(candidates) < max(6, limit // 2):
        candidates = [t for t in with_signal if _effective_hike_miles_upper(t) <= max_miles * 1.2]

    if not candidates:
        candidates = with_signal[:]

    def eff(t: Any) -> float:
        return _effective_hike_miles_upper(t)

    short = [t for t in candidates if eff(t) <= max_miles * 0.33]
    med = [t for t in candidates if max_miles * 0.33 < eff(t) <= max_miles * 0.66]
    long = [t for t in candidates if max_miles * 0.66 < eff(t) <= max_miles * 1.2]

    for b in (short, med, long):
        b.sort(key=eff, reverse=True)

    picked: List[Any] = []
    per_bucket = max(1, limit // 3)

    for b in (short, med, long):
        picked.extend(b[:per_bucket])

    target = max_miles * 0.7
    remaining = [t for t in candidates if t not in picked]
    remaining.sort(
        key=lambda t: (
            not _has_multi_segment_structure(t),
            abs(eff(t) - target),
        )
    )
    picked.extend(remaining[: max(0, limit - len(picked))])

    return picked[:limit]


def _format_trail_distance_label(t: Any) -> str:
    """
    User-facing distance label in hiking terms (no dataset/geometry talk).
    Prefer:
      - loops: ~X mi
      - everything else: ~X–~2X mi (shorter vs longer / turnaround / variant)
    """
    rc = getattr(t, "route_class", "unknown")

    loop = getattr(t, "loop_miles", None)
    ow = getattr(t, "one_way_miles", None)
    span = getattr(t, "span_miles", None)
    tot = getattr(t, "total_miles", None)

    if rc == "loop" and isinstance(loop, (int, float)) and loop > 0:
        return f"~{loop:.1f} mi"

    if isinstance(ow, (int, float)) and ow > 0:
        return f"~{ow:.1f}–{(2.0 * ow):.1f} mi"

    if isinstance(span, (int, float)) and span > 0:
        return f"~{span:.1f}–{(2.0 * span):.1f} mi"

    if isinstance(tot, (int, float)) and tot > 0:
        return f"up to ~{tot:.1f} mi"

    return "distance varies"


def _format_trail_options(trails: List[Any], constraints: Dict[str, Any], limit: int = 12) -> str:
    selected = _select_trails_for_prompt(trails, constraints, limit=limit)

    if not selected:
        return "Suggested trail options: none found.\n\n"

    lines = ["Suggested trail options (estimated round-trip distances):"]

    for t in selected:
        name = getattr(t, "name", None) or str(t)
        label = _format_trail_distance_label(t)
        lines.append(f"- {name} ({label})")

    return "\n".join(lines) + "\n\n"


# --- Main prompt builder ------------------------------------------------------

def build_trip_advice_prompt(context: Dict[str, Any]) -> str:
    trip: TripRequest = context["trip"]
    scores: Scores = context["scores"]
    alerts: List[Alert] = context["alerts"]
    chunks: List[DocumentChunk] = context["rag_chunks"]
    weather: List[WeatherDay] = context["weather"]

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

    weather_text = _format_weather_section(weather)

    if alerts:
        alerts_text = "Current NPS alerts:\n"
        for a in alerts[:5]:
            alerts_text += f"- [{a.category}] {a.title}\n"
            if a.summary:
                alerts_text += f"  {a.summary[:200].replace(chr(10), ' ')}...\n"
    else:
        alerts_text = "Current NPS alerts: none returned.\n"

    if chunks:
        rag_text = "Relevant official information snippets:\n"
        for i, c in enumerate(chunks[:5]):
            rag_text += f"[Snippet {i+1}] Source: {c.source or 'NPS article'}\n"
            rag_text += c.text[:400].replace("\n", " ") + "\n\n"
    else:
        rag_text = "No additional official documentation snippets retrieved.\n"

    trails = context.get("trail_cards", [])
    trails_text = _format_trail_options(trails, trip.constraints or {}, limit=12)

    instructions = (
        "Using ONLY the information above, answer the following:\n"
        "1) Give a verdict: GO, GO-WITH-CAUTION, or AVOID.\n"
        "2) Explain your verdict in 2–4 short paragraphs.\n"
        "3) Call out specific risks (weather, access, seasonality) and how to mitigate them.\n"
        "4) Suggest 2–4 specific trail options BY NAME.\n"
        "   - You MUST choose trail names ONLY from the 'Suggested trail options' list above.\n"
        "   - Do NOT invent trail names.\n"
        "   - Use the distance ranges shown (these are estimates). If helpful, note that some hikes\n"
        "     can be shortened by turning around earlier.\n"
        "5) List 3–6 concrete safety or gear recommendations.\n"
        "6) If information above is missing or uncertain, say so clearly.\n"
    )

    return (
        header
        + scores_text + "\n"
        + weather_text + "\n"
        + alerts_text + "\n"
        + rag_text + "\n"
        + trails_text
        + instructions
    )
