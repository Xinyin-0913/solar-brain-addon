"""Placeholder solar recommendation logic.

Rule priority (highest first):
1. High wind  -> safe mode (safety always wins)
2. Low solar forecast -> save battery
3. Solar window (10:00-15:00) -> use solar energy
4. Otherwise -> monitor / no action
"""

import logging
from datetime import datetime

from .models import Recommendation, WeatherData

logger = logging.getLogger("solar_brain.logic")

HIGH_WIND_KMH = 40.0
LOW_FORECAST_KWH = 2.0
SOLAR_WINDOW_START = 10
SOLAR_WINDOW_END = 15


def get_recommendation(weather: WeatherData, now: datetime | None = None) -> Recommendation:
    """Compute a solar recommendation from current time and weather."""
    now = now or datetime.now()
    hour = now.hour

    if weather.wind_speed_kmh > HIGH_WIND_KMH:
        rec = Recommendation(
            recommendation_text="High wind detected. Switch to safe mode.",
            suggested_action="enable_safe_mode",
            risk_level="high",
            reason=f"Wind speed is {weather.wind_speed_kmh:.0f} km/h "
                   f"(threshold {HIGH_WIND_KMH:.0f} km/h).",
        )
    elif weather.forecast_solar_kwh < LOW_FORECAST_KWH:
        rec = Recommendation(
            recommendation_text="Low solar production expected. Conserve battery.",
            suggested_action="save_battery",
            risk_level="medium",
            reason=f"Forecast solar production is {weather.forecast_solar_kwh:.1f} kWh "
                   f"(threshold {LOW_FORECAST_KWH:.1f} kWh).",
        )
    elif SOLAR_WINDOW_START <= hour <= SOLAR_WINDOW_END:
        rec = Recommendation(
            recommendation_text="Peak solar window. Use solar energy now.",
            suggested_action="use_solar_energy",
            risk_level="low",
            reason=f"Current hour ({hour}:00) is inside the solar window "
                   f"({SOLAR_WINDOW_START}:00-{SOLAR_WINDOW_END}:00).",
        )
    else:
        rec = Recommendation(
            recommendation_text="Outside peak solar hours. No action needed.",
            suggested_action="monitor",
            risk_level="low",
            reason=f"Current hour ({hour}:00) is outside the solar window and "
                   f"conditions are normal.",
        )

    logger.info("Recommendation: %s (risk=%s)", rec.suggested_action, rec.risk_level)
    return rec
