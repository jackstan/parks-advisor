from typing import List, Tuple

from .models import TripRequest, WeatherDay, Alert, Scores


# Centralized weights so you can tweak them in one place
WEIGHTS = {
    "access": 0.4,   # closures, harsh conditions, etc.
    "weather": 0.6,  # temp, precip, wind
}

# Reasonable bounds for hiking comfort (Yosemite-ish defaults) — in °F
COMFORT_TEMP_MIN = 35.0   # F
COMFORT_TEMP_MAX = 85.0   # F

# Wind thresholds (mph)
WIND_BREEZY = 15.0
WIND_STRONG = 30.0


# --- helpers to convert from your metric WeatherDay fields --------------------

def c_to_f(c: float) -> float:
    return (c * 9 / 5) + 32

def mps_to_mph(mps: float) -> float:
    return mps * 2.23694

def prob_to_pct(p: float) -> float:
    # your precip_probability is 0–1, this converts to 0–100
    return p * 100.0


def _score_weather(days: List[WeatherDay]) -> Tuple[float, List[str], List[str]]:
    """
    Return (weather_score, risk_flags, notes)
    Score in [0, 100] based on temperature, precip, and wind.

    Uses your metric fields from WeatherDay, but thresholds are set in °F + mph.
    """
    if not days:
        return 70.0, ["weather_uncertain"], ["No forecast data; defaulting weather score to 70."]

    notes: List[str] = []
    risk_flags: List[str] = []

    temps_ok = 0
    temps_bad = 0
    wet_days = 0
    very_windy = 0

    for d in days:
        # Convert from metric model fields to the units our thresholds use
        temp_max_f = c_to_f(d.temp_max_c)
        precip_prob_pct = prob_to_pct(d.precip_probability)
        wind_max_mph = mps_to_mph(d.wind_speed_max_mps)

        # Temperature comfort
        if COMFORT_TEMP_MIN <= temp_max_f <= COMFORT_TEMP_MAX:
            temps_ok += 1
        else:
            temps_bad += 1
            notes.append(
                f"Day {d.date}: temp max {temp_max_f:.0f}°F outside comfort band "
                f"({COMFORT_TEMP_MIN:.0f}–{COMFORT_TEMP_MAX:.0f}°F)."
            )

        # Precipitation
        if precip_prob_pct >= 40:
            wet_days += 1
            notes.append(
                f"Day {d.date}: {precip_prob_pct:.0f}% chance of precipitation "
                f"(bring rain gear / adjust plans)."
            )

        # Wind
        if wind_max_mph >= WIND_STRONG:
            very_windy += 1
            notes.append(
                f"Day {d.date}: winds up to {wind_max_mph:.0f} mph "
                f"(exposed ridges may be unsafe)."
            )
        elif wind_max_mph >= WIND_BREEZY:
            notes.append(
                f"Day {d.date}: breezy conditions (up to {wind_max_mph:.0f} mph)."
            )

    n_days = len(days)

    # Base weather score
    score = 85.0

    # Penalize bad temps
    if temps_bad > 0:
        frac_bad = temps_bad / n_days
        score -= 20.0 * frac_bad
        risk_flags.append("temp_extreme")

    # Penalize wet days
    if wet_days > 0:
        frac_wet = wet_days / n_days
        score -= 15.0 * frac_wet
        risk_flags.append("rain_risk")

    # Penalize wind
    if very_windy > 0:
        frac_v_wind = very_windy / n_days
        score -= 15.0 * frac_v_wind
        risk_flags.append("wind_risk")

    # Clamp
    score = max(0.0, min(100.0, score))

    # If we have any serious risks, add a generic weather_risk flag
    if any(f in risk_flags for f in ("temp_extreme", "rain_risk", "wind_risk")):
        risk_flags.append("weather_risk")

    return score, risk_flags, notes


def _score_access(alerts: List[Alert]) -> Tuple[float, List[str], List[str]]:
    """
    Return (access_score, risk_flags, notes)
    Penalize closures/major alerts; otherwise start from a high base.
    """
    if not alerts:
        return 95.0, [], ["No active park alerts returned."]

    notes: List[str] = []
    risk_flags: List[str] = []
    score = 95.0

    closure_alerts = [a for a in alerts if "closure" in a.category.lower()]
    other_alerts = [a for a in alerts if a not in closure_alerts]

    # Penalize for closures
    if closure_alerts:
        n = len(closure_alerts)
        score -= 15.0 + 5.0 * (n - 1)  # first closure is a big hit, others smaller
        notes.append(
            f"There are {n} closure-related alerts; some roads or trails may be unavailable."
        )
        for a in closure_alerts:
            notes.append(f"Closure: {a.title}")

        risk_flags.append("access_risk")

    # Other alerts are informational but still noteworthy
    for a in other_alerts:
        notes.append(f"Alert: {a.title}")

    score = max(0.0, min(100.0, score))
    return score, risk_flags, notes


def compute_scores(
    trip: TripRequest,
    weather_days: List[WeatherDay],
    alerts: List[Alert],
) -> Scores:
    """
    Compute access_score, weather_score, trip_readiness_score, risk_flags, notes,
    plus the extra fields required by Scores:
      - park_code
      - start_date
      - end_date
      - risk_score
      - crowd_score (placeholder for now)
    """
    weather_score, weather_flags, weather_notes = _score_weather(weather_days)
    access_score, access_flags, access_notes = _score_access(alerts)

    # Weighted blend for overall trip readiness
    trip_readiness = (
        WEIGHTS["weather"] * weather_score +
        WEIGHTS["access"] * access_score
    )
    trip_readiness = max(0.0, min(100.0, trip_readiness))

    # Merge flags and notes
    risk_flags = list(set(weather_flags + access_flags))
    notes = weather_notes + access_notes

    # --- New fields your Scores model expects ---------------------------------

    # Placeholder for now: we haven’t modeled crowding yet.
    # You can later plug in something based on season, weekend/weekday, etc.
    crowd_score = 50.0

    # Simple first pass for risk_score:
    # interpret it as "inverse of readiness" so higher readiness => lower risk.
    risk_score = max(0.0, min(100.0, 100.0 - trip_readiness))

    return Scores(
        park_code=trip.park_code,
        start_date=trip.start_date,
        end_date=trip.end_date,
        access_score=access_score,
        weather_score=weather_score,
        crowd_score=crowd_score,
        risk_score=risk_score,
        trip_readiness_score=trip_readiness,
        risk_flags=risk_flags,
        notes=notes,
    )
