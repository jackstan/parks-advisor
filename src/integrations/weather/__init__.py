"""
Weather integration layer.

Wraps Open-Meteo client in domain-agnostic API.
Decouples weather fetching from domain logic.
"""

from typing import List
from ...models import WeatherDay


def get_weather_for_location(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    location_id: str = "unknown",
) -> List[WeatherDay]:
    """
    Fetch weather for any location (climbing crag, hiking park, ski zone, etc.).
    
    This is a thin wrapper around the legacy get_weather_for_trip that
    replaces park-code lookup with direct lat/lon.
    
    Args:
        lat: Latitude
        lon: Longitude
        start_date: ISO format start date
        end_date: ISO format end date
        location_id: Identifier for the location (used in WeatherDay.location_id field)
    
    Returns:
        List of WeatherDay objects with weather data
    """
    # Import here to avoid circular dependency
    import requests
    from datetime import date
    
    # Basic sanity check on dates
    try:
        start_dt = date.fromisoformat(start_date)
        end_dt = date.fromisoformat(end_date)
        if end_dt < start_dt:
            raise ValueError("end_date before start_date")
    except Exception:
        # Fallback: next 7 days
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
                # Use location_id instead of park_code
                park_code=location_id,  # Keep old field name for backward compat
                date=day,
                temp_min_c=temp_min[i] if i < len(temp_min) else 20.0,
                temp_max_c=temp_max[i] if i < len(temp_max) else 25.0,
                precip_mm=precip_sum[i] if i < len(precip_sum) else 0.0,
                precip_probability=precip_prob[i] / 100.0 if i < len(precip_prob) else 0.0,
                wind_speed_max_mps=wind_max[i] if i < len(wind_max) else 0.0,
                thunderstorm_probability=0.0,  # Not provided by Open-Meteo
                snowfall_cm=0.0,  # Not provided by Open-Meteo; could estimate from temp
            )
        )

    return weather_days
