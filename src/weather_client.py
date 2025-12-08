from typing import List, Optional
from datetime import date

import requests

from .config import PARKS
from .models import WeatherDay


def get_weather_for_trip(park_code: str, start_date: str, end_date: str) -> List[WeatherDay]:
    """
    Fetch daily weather forecasts from Open-Meteo for the requested trip window.

    We now:
      - respect the start_date and end_date passed in
      - ask Open-Meteo specifically for that date range
    """
    park = PARKS[park_code]
    lat = park["lat"]
    lon = park["lon"]

    # Basic sanity check: if dates look weird, just fall back to "next 7 days"
    try:
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)
        if end_dt < start_dt:
            raise ValueError("end_date before start_date")
    except Exception:
        # Fallback behavior: next 7 days from now
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "windspeed_10m_max",
                ]
            ),
            "timezone": "auto",
            "forecast_days": 7,
        }
    else:
        # Normal case: request exactly the trip window
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": ",".join(
                [
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "precipitation_probability_max",
                    "windspeed_10m_max",
                ]
            ),
            "timezone": "auto",
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat(),
        }

    resp = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    temp_min = daily.get("temperature_2m_min", [])
    temp_max = daily.get("temperature_2m_max", [])
    precip_sum = daily.get("precipitation_sum", [])
    precip_prob = daily.get("precipitation_probability_max", [])
    wind_max = daily.get("windspeed_10m_max", [])

    weather_days: List[WeatherDay] = []

    for i, day in enumerate(dates):
        weather_days.append(
            WeatherDay(
                park_code=park_code,
                date=day,
                temp_min_c=temp_min[i],
                temp_max_c=temp_max[i],
                precip_mm=precip_sum[i],
                precip_probability=(precip_prob[i] / 100.0 if precip_prob[i] is not None else 0.0),
                wind_speed_max_mps=_kmh_to_mps(wind_max[i]),
                thunderstorm_probability=0.0,  # placeholder for now
                snowfall_cm=0.0,
                heat_index_risk=_classify_heat(temp_max[i]),
                storm_risk=_classify_storm(precip_prob[i], wind_max[i]),
                visibility_risk="low",
            )
        )

    return weather_days


def _kmh_to_mps(speed_kmh: float) -> float:
    if speed_kmh is None:
        return 0.0
    return speed_kmh / 3.6


def _classify_heat(temp_max_c: float) -> str:
    if temp_max_c >= 32:
        return "high"
    if temp_max_c >= 26:
        return "medium"
    return "low"


def _classify_storm(precip_prob: Optional[float], wind_kmh: Optional[float]) -> str:
    precip_prob = precip_prob or 0
    wind_kmh = wind_kmh or 0

    if precip_prob >= 70 and wind_kmh >= 30:
        return "high"
    if precip_prob >= 40 or wind_kmh >= 20:
        return "medium"
    return "low"
