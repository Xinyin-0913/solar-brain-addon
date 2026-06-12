"""Weather client.

Uses the free Open-Meteo API (no key needed) when a location is configured.
Falls back to safe stub values on any failure, so the add-on always works.
"""

import logging

import httpx

from .models import AddonConfig, WeatherData

logger = logging.getLogger("solar_brain.weather")

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# Stub values used when no location is configured or the API is unreachable.
STUB_WEATHER = WeatherData(wind_speed_kmh=10.0, forecast_solar_kwh=4.5, source="stub")

# Very rough placeholder: convert daily shortwave radiation (MJ/m^2) to an
# estimated production in kWh for a small residential PV system.
RADIATION_TO_KWH_FACTOR = 0.35


async def get_weather(config: AddonConfig) -> WeatherData:
    """Fetch current wind speed and today's solar forecast for the configured location."""
    if not config.has_location:
        logger.info("No location configured, using stub weather data")
        return STUB_WEATHER

    params = {
        "latitude": config.latitude,
        "longitude": config.longitude,
        "current": "wind_speed_10m",
        "daily": "shortwave_radiation_sum",
        "wind_speed_unit": "kmh",
        "forecast_days": 1,
        "timezone": "auto",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(OPEN_METEO_URL, params=params)
            response.raise_for_status()
            data = response.json()

        wind_speed = float(data["current"]["wind_speed_10m"])
        radiation_sum = float(data["daily"]["shortwave_radiation_sum"][0])
        weather = WeatherData(
            wind_speed_kmh=wind_speed,
            forecast_solar_kwh=round(radiation_sum * RADIATION_TO_KWH_FACTOR, 2),
            source="open-meteo",
        )
        logger.info(
            "Weather: wind=%.1f km/h, forecast=%.2f kWh (open-meteo)",
            weather.wind_speed_kmh,
            weather.forecast_solar_kwh,
        )
        return weather
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as err:
        logger.warning("Weather fetch failed, using stub data: %s", err)
        return STUB_WEATHER.model_copy(update={"source": "fallback"})
