from .models import TripRequest, Scores
from .weather_client import get_weather_for_trip
from .scoring import compute_scores
from .nps_client import get_alerts_for_park


def advise_trip(trip: TripRequest) -> tuple[Scores, str]:
    """
    High-level advisor:
    - fetch weather for the trip
    - compute scores
    - return scores + a simple recommendation summary

    We'll later swap the string summary for an LLM-generated explanation.
    """
    # 1) Get weather data for this park and dates
    weather_days = get_weather_for_trip(trip.park_code, trip.start_date, trip.end_date)
    # 2) Get alerts for this park
    alerts = get_alerts_for_park(trip.park_code)
    # 3) Compute numeric scores from that weather
    scores = compute_scores(trip, weather_days, alerts)

    # 4) Turn the scores into a coarse recommendation label
    if scores.trip_readiness_score >= 75:
        verdict = "go"
    elif scores.trip_readiness_score >= 55:
        verdict = "use_with_caution"
        # You could branch on risk_flags here later
    else:
        verdict = "avoid"

    # 4) Build a human-readable summary using the numbers + notes
    summary = (
        f"Trip readiness: {scores.trip_readiness_score:.0f} ({verdict}). "
        f"Weather score: {scores.weather_score:.0f}. "
    )
    if scores.notes:
        summary += " " + " ".join(scores.notes)

    return scores, summary
