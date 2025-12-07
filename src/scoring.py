from typing import List

from .models import WeatherDay, Scores, TripRequest, Alert


def compute_scores(
    trip: TripRequest,
    weather_days: List[WeatherDay],
    alerts: List[Alert],
) -> Scores:
    """
    Take raw weather + alerts for the trip and turn them into:
    - weather_score
    - access_score
    - risk_score
    - crowd_score (stub)
    - trip_readiness_score
    - risk_flags + notes explaining why

    This is intentionally simple and opinionated so you can iterate on it later.
    """
    notes: List[str] = []
    access_notes: List[str] = []

    # -------------------------
    # 1) WEATHER SCORE
    # -------------------------
    # Start with a high baseline and subtract for bad conditions.
    weather_score = 90.0

    if not weather_days:
        # If for some reason we didn't get weather, be conservative.
        weather_score = 60.0
        notes.append("No weather data available; using conservative default.")
    else:
        max_temp = max(w.temp_max_c for w in weather_days)
        max_precip_prob = max(w.precip_probability for w in weather_days)

        # Temperature penalties
        if max_temp >= 32:
            weather_score -= 25
            notes.append("High temperatures; heat risk for strenuous hikes.")
        elif max_temp >= 26:
            weather_score -= 10
            notes.append("Warm temperatures; plan for sun and extra hydration.")

        # Precipitation penalties
        if max_precip_prob >= 0.7:
            weather_score -= 25
            notes.append("High chance of precipitation; storms or heavy rain likely.")
        elif max_precip_prob >= 0.4:
            weather_score -= 10
            notes.append("Moderate chance of rain; pack appropriate gear.")

    # Clamp to [0, 100]
    weather_score = max(0.0, min(100.0, weather_score))

    # -------------------------
    # 2) ACCESS SCORE (ALERTS)
    # -------------------------
    access_score = 90.0

    # "Major" alerts are things like road/trail closures, fire, flood, etc.
    major_alerts = [a for a in alerts if a.is_major]

    if major_alerts:
        # Each major alert drags access_score down.
        access_score -= 15.0 * len(major_alerts)
        if access_score < 0:
            access_score = 0.0

        access_notes.append(
            f"{len(major_alerts)} major access-impacting alerts (e.g., closures or hazards)."
        )

    # -------------------------
    # 3) RISK & CROWD SCORES
    # -------------------------
    # For now, risk_score is just inverse of weather_score.
    # Later you can fold in trail difficulty, user profile, etc.
    risk_score = 100.0 - weather_score

    # Crowd score is still a stub until we plug in visitation data.
    crowd_score = 50.0

    # -------------------------
    # 4) TRIP READINESS SCORE
    # -------------------------
    # Weighted combo of access, weather, and "inverse risk".
    trip_readiness = (
        0.5 * access_score +
        0.3 * weather_score +
        0.2 * (100.0 - risk_score)
    )

    # -------------------------
    # 5) RISK FLAGS + NOTES
    # -------------------------
    risk_flags: List[str] = []

    if weather_score < 70:
        risk_flags.append("weather_risk")
    if major_alerts:
        risk_flags.append("access_risk")

    return Scores(
        park_code=trip.park_code,
        start_date=trip.start_date,
        end_date=trip.end_date,
        access_score=access_score,
        weather_score=weather_score,
        risk_score=risk_score,
        crowd_score=crowd_score,
        trip_readiness_score=trip_readiness,
        risk_flags=risk_flags,
        notes=notes + access_notes,
    )
