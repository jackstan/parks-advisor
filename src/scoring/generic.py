"""
Generic scoring utilities: unit conversions, common thresholds, etc.

These are reusable across domains (climbing, hiking, skiing).
"""


def c_to_f(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (c * 9 / 5) + 32


def f_to_c(f: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (f - 32) * 5 / 9


def mps_to_mph(mps: float) -> float:
    """Convert meters/second to miles/hour."""
    return mps * 2.23694


def mph_to_mps(mph: float) -> float:
    """Convert miles/hour to meters/second."""
    return mph / 2.23694


def prob_to_pct(p: float) -> float:
    """Convert probability (0–1) to percentage (0–100)."""
    return p * 100.0


def pct_to_prob(pct: float) -> float:
    """Convert percentage (0–100) to probability (0–1)."""
    return pct / 100.0


# Common weather thresholds (all in Celsius and m/s; convert as needed)

TEMPERATURE_COMFORT_MIN_C = 10.0  # ~50°F
TEMPERATURE_COMFORT_MAX_C = 25.0  # ~77°F

WIND_BREEZY_MPS = 6.7   # ~15 mph
WIND_STRONG_MPS = 13.4  # ~30 mph

PRECIP_LIGHT_MM = 2.5
PRECIP_MODERATE_MM = 10.0
PRECIP_HEAVY_MM = 25.0
