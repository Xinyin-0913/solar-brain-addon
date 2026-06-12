"""Pydantic models and add-on configuration loading."""

import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger("solar_brain.models")

# Home Assistant Supervisor mounts add-on options here.
OPTIONS_FILE = Path("/data/options.json")


class AddonConfig(BaseModel):
    """Add-on configuration, from HA options or environment variables."""

    # Local development ONLY (env vars). In add-on mode the Supervisor
    # provides API access automatically and these are ignored.
    home_assistant_url: str = ""
    home_assistant_token: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    electricity_import_price_eur_per_kwh: float = 0.30
    feed_in_tariff_eur_per_kwh: float = 0.08
    system_cost_eur: float = 0.0
    installation_date: str = ""  # YYYY-MM-DD, informational
    openrouter_api_key: str = ""
    enable_ai: bool = False

    @property
    def has_location(self) -> bool:
        return self.latitude != 0.0 or self.longitude != 0.0

    @classmethod
    def load(cls) -> "AddonConfig":
        """Load config from /data/options.json (HA add-on) or env vars (local run)."""
        if OPTIONS_FILE.exists():
            try:
                raw = json.loads(OPTIONS_FILE.read_text())
                config = cls(**{k: v for k, v in raw.items() if v is not None})
                logger.info("Loaded configuration from %s", OPTIONS_FILE)
                return config
            except (json.JSONDecodeError, ValueError) as err:
                logger.error("Invalid options.json, falling back to defaults: %s", err)

        config = cls(
            home_assistant_url=os.getenv("HOME_ASSISTANT_URL", ""),
            home_assistant_token=os.getenv("HOME_ASSISTANT_TOKEN", ""),
            latitude=float(os.getenv("LATITUDE", "0") or 0),
            longitude=float(os.getenv("LONGITUDE", "0") or 0),
            electricity_import_price_eur_per_kwh=float(
                os.getenv("ELECTRICITY_IMPORT_PRICE_EUR_PER_KWH", "0.30") or 0.30
            ),
            feed_in_tariff_eur_per_kwh=float(
                os.getenv("FEED_IN_TARIFF_EUR_PER_KWH", "0.08") or 0.08
            ),
            system_cost_eur=float(os.getenv("SYSTEM_COST_EUR", "0") or 0),
            installation_date=os.getenv("INSTALLATION_DATE", ""),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            enable_ai=os.getenv("ENABLE_AI", "false").lower() in ("1", "true", "yes"),
        )
        logger.info("Loaded configuration from environment variables")
        return config


class WeatherData(BaseModel):
    """Simplified weather snapshot used by the solar logic."""

    wind_speed_kmh: float
    forecast_solar_kwh: float
    source: str = "stub"


class Recommendation(BaseModel):
    """Response model for GET /api/recommendation."""

    recommendation_text: str
    suggested_action: str
    risk_level: str  # low | medium | high
    reason: str


class StatusResponse(BaseModel):
    """Response model for GET /api/status."""

    addon_status: str
    current_time: str
    location: str
    solar_recommendation: str
    ha_mode: str        # "addon" | "local"
    ha_auth: str        # "supervisor_token" | "manual_token" | "not_configured"
    ha_connection: str  # user-facing copy for the connection mode
    ha_reachable: bool  # live API reachability check


# Telemetry roles a Home Assistant entity can be mapped to.
TELEMETRY_ROLES = [
    "solar_power",
    "battery_soc",
    "grid_import_power",
    "grid_export_power",
    "ev_power",
    "home_load_power",
]

# role -> field name on TelemetrySnapshot
ROLE_TO_FIELD = {
    "solar_power": "solar_power_w",
    "battery_soc": "battery_soc",
    "grid_import_power": "grid_import_w",
    "grid_export_power": "grid_export_w",
    "ev_power": "ev_power_w",
    "home_load_power": "home_load_w",
}


class TelemetrySnapshot(BaseModel):
    """Normalized telemetry snapshot (all power values in watts, SOC in %)."""

    timestamp: str
    solar_power_w: float | None = None
    battery_soc: float | None = None
    grid_import_w: float | None = None
    grid_export_w: float | None = None
    home_load_w: float | None = None
    ev_power_w: float | None = None
    # Transparency about data quality:
    missing_roles: list[str] = []     # roles with no mapping or no usable value
    estimated_fields: list[str] = []  # fields computed instead of measured


class MappingUpdate(BaseModel):
    """Request body for POST /api/entities/mapping.

    Maps role -> entity_id; a null value clears that role's mapping.
    """

    mappings: dict[str, str | None]


# --- Savings engine ----------------------------------------------------------

# Shipped defaults. When the user's tariff still equals these, the UI shows
# a "check your tariff" banner (we can't tell "kept default" from "really
# pays 0.30", so the banner is informational).
DEFAULT_IMPORT_PRICE_EUR_PER_KWH = 0.30
DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH = 0.08


class SavingsPrices(BaseModel):
    """Tariff settings the calculations were made with."""

    import_eur_per_kwh: float
    feed_in_eur_per_kwh: float


class SavingsCurrent(BaseModel):
    """Response model for GET /api/savings/current (instantaneous rates)."""

    timestamp: str
    self_consumption_w: float | None
    export_w: float | None
    savings_per_hour_eur: float | None          # self-consumption value only
    export_earnings_per_hour_eur: float | None
    total_benefit_per_hour_eur: float | None
    prices: SavingsPrices


class PeriodSavings(BaseModel):
    """Integrated energy and money for one time period."""

    self_consumption_kwh: float
    export_kwh: float
    solar_kwh: float
    self_consumption_savings_eur: float
    export_earnings_eur: float
    total_benefit_eur: float
    data_coverage_hours: float  # how much of the period had usable data


class PaybackStatus(BaseModel):
    system_cost_eur: float
    recovered_eur: float
    progress_percent: float | None       # None when system_cost not configured
    estimated_payback_date: str | None   # None until enough data / no cost set


class SavingsWarning(BaseModel):
    """A transparency banner shown on the savings detail page."""

    code: str      # low_data_coverage | default_tariff | no_system_cost | no_payback_estimate
    severity: str  # "warning" | "info"
    message: str


class SavingsDetail(BaseModel):
    """Response model for GET /api/savings/detail?period=..."""

    period: str                    # today | week | month | lifetime
    period_start: str | None       # UTC ISO; None for lifetime with no data
    period_end: str                # UTC ISO (now)
    savings: PeriodSavings
    elapsed_hours: float | None    # wall-clock hours in the period so far
    coverage_percent: float | None # data_coverage_hours / elapsed_hours
    warnings: list[SavingsWarning]
    tariff_is_default: bool
    prices: SavingsPrices
    formulas: dict[str, str]       # the math, stated on the record


class SavingsSummary(BaseModel):
    """Response model for GET /api/savings/summary."""

    timestamp: str
    today: PeriodSavings
    this_week: PeriodSavings
    this_month: PeriodSavings
    lifetime: PeriodSavings
    average_daily_benefit_eur: float | None   # None with < 1 day of data
    estimated_annual_savings_eur: float | None
    payback: PaybackStatus
    measured_since: str | None                # ts of first telemetry snapshot
    installation_date: str | None
    prices: SavingsPrices
