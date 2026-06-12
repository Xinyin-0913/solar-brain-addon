"""Quick smoke test for solar logic rules and weather client."""

import asyncio
from datetime import datetime

from app.models import AddonConfig, WeatherData
from app.solar_logic import get_recommendation
from app.weather_client import get_weather

noon = datetime(2026, 6, 12, 12, 0)
night = datetime(2026, 6, 12, 20, 0)

r = get_recommendation(WeatherData(wind_speed_kmh=50, forecast_solar_kwh=5), noon)
assert r.suggested_action == "enable_safe_mode" and r.risk_level == "high", r
r = get_recommendation(WeatherData(wind_speed_kmh=10, forecast_solar_kwh=1.0), noon)
assert r.suggested_action == "save_battery", r
r = get_recommendation(WeatherData(wind_speed_kmh=10, forecast_solar_kwh=5), noon)
assert r.suggested_action == "use_solar_energy", r
r = get_recommendation(WeatherData(wind_speed_kmh=10, forecast_solar_kwh=5), night)
assert r.suggested_action == "monitor", r
print("solar_logic: all 4 rules OK")

cfg = AddonConfig(latitude=52.52, longitude=13.40)
w = asyncio.run(get_weather(cfg))
print(f"weather: source={w.source} wind={w.wind_speed_kmh} kwh={w.forecast_solar_kwh}")
