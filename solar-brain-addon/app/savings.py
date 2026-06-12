"""Savings Engine V1 - every euro derived from measured telemetry.

Principles:
- No fake numbers: only integrates stored snapshots; gaps in the data
  reduce the result instead of being interpolated away.
- Transparency: every response carries the prices used, the data coverage,
  and None (never a guess) when there is not enough data.

All formulas are documented in docs/savings_engine.md - keep them in sync.
"""

import logging
from datetime import datetime, timedelta, timezone

from . import database
from .models import (
    DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH,
    DEFAULT_IMPORT_PRICE_EUR_PER_KWH,
    AddonConfig,
    PaybackStatus,
    PeriodSavings,
    SavingsCurrent,
    SavingsDetail,
    SavingsPrices,
    SavingsSummary,
    SavingsWarning,
    TelemetrySnapshot,
)

logger = logging.getLogger("solar_brain.savings")

# A gap between snapshots longer than this means the add-on (or sensor) was
# down; we only credit MAX_GAP_SECONDS of it instead of extrapolating across.
MAX_GAP_SECONDS = 300.0

# Below this much observed history, annual/payback projections are refused.
MIN_OBSERVATION_DAYS = 1.0

# Detail-page transparency thresholds.
DETAIL_PERIODS = ("today", "week", "month", "lifetime")
LOW_COVERAGE_PERCENT = 50.0
MIN_ELAPSED_HOURS_FOR_COVERAGE_WARNING = 1.0

# Stated on the record in every detail response (and on the /savings page).
FORMULAS = {
    "self_consumption_savings": "self-consumed kWh × import price",
    "export_earnings": "exported kWh × feed-in tariff",
    "total_value": "self-consumption savings + export earnings",
    "energy_integration": (
        "energy = Σ power(tᵢ) × min(tᵢ₊₁ − tᵢ, 300 s); gaps longer than "
        "300 s are not credited beyond that"
    ),
}

WS_PER_KWH = 3_600_000.0  # watt-seconds per kWh


def _prices(config: AddonConfig) -> SavingsPrices:
    return SavingsPrices(
        import_eur_per_kwh=config.electricity_import_price_eur_per_kwh,
        feed_in_eur_per_kwh=config.feed_in_tariff_eur_per_kwh,
    )


def integrate_energy(snapshots: list[dict]) -> dict:
    """Left-rectangle integration of power snapshots into energy (kWh).

    For each pair of consecutive snapshots, the power of the EARLIER one is
    assumed to hold for the interval, capped at MAX_GAP_SECONDS:

        E += P(t_i) * min(t_{i+1} - t_i, 300 s)

    Self-consumption power is min(solar, load); negative powers clamp to 0.
    Snapshots with missing values contribute nothing for those fields.
    """
    sc_ws = 0.0
    export_ws = 0.0
    solar_ws = 0.0
    covered_s = 0.0

    for current, nxt in zip(snapshots, snapshots[1:]):
        try:
            t1 = datetime.fromisoformat(current["ts"])
            t2 = datetime.fromisoformat(nxt["ts"])
        except (ValueError, TypeError):
            logger.warning("Skipping snapshot with bad timestamp: %s", current.get("ts"))
            continue
        dt = (t2 - t1).total_seconds()
        if dt <= 0:
            continue
        dt = min(dt, MAX_GAP_SECONDS)

        solar = current.get("solar_power_w")
        load = current.get("home_load_w")
        export = current.get("grid_export_w")

        usable = False
        if solar is not None:
            solar_ws += max(solar, 0.0) * dt
            usable = True
            if load is not None:
                sc_ws += max(min(solar, load), 0.0) * dt
        if export is not None:
            export_ws += max(export, 0.0) * dt
            usable = True
        if usable:
            covered_s += dt

    return {
        "self_consumption_kwh": sc_ws / WS_PER_KWH,
        "export_kwh": export_ws / WS_PER_KWH,
        "solar_kwh": solar_ws / WS_PER_KWH,
        "covered_hours": covered_s / 3600.0,
    }


def period_savings(snapshots: list[dict], prices: SavingsPrices) -> PeriodSavings:
    """Money for one period: energy totals x tariffs."""
    energy = integrate_energy(snapshots)
    sc_eur = energy["self_consumption_kwh"] * prices.import_eur_per_kwh
    export_eur = energy["export_kwh"] * prices.feed_in_eur_per_kwh
    return PeriodSavings(
        self_consumption_kwh=round(energy["self_consumption_kwh"], 3),
        export_kwh=round(energy["export_kwh"], 3),
        solar_kwh=round(energy["solar_kwh"], 3),
        self_consumption_savings_eur=round(sc_eur, 4),
        export_earnings_eur=round(export_eur, 4),
        total_benefit_eur=round(sc_eur + export_eur, 4),
        data_coverage_hours=round(energy["covered_hours"], 2),
    )


def current_savings(snapshot: TelemetrySnapshot, config: AddonConfig) -> SavingsCurrent:
    """Instantaneous savings rates from a live telemetry snapshot.

    self_consumption_w   = min(solar_power_w, home_load_w), clamped at >= 0
    savings_per_hour_eur = self_consumption_w / 1000 * import_price
    export earnings/hour = grid_export_w / 1000 * feed_in_tariff
    """
    prices = _prices(config)

    sc_w: float | None = None
    if snapshot.solar_power_w is not None and snapshot.home_load_w is not None:
        sc_w = max(min(snapshot.solar_power_w, snapshot.home_load_w), 0.0)

    export_w: float | None = None
    if snapshot.grid_export_w is not None:
        export_w = max(snapshot.grid_export_w, 0.0)

    sc_rate = (
        round(sc_w / 1000.0 * prices.import_eur_per_kwh, 4) if sc_w is not None else None
    )
    export_rate = (
        round(export_w / 1000.0 * prices.feed_in_eur_per_kwh, 4)
        if export_w is not None
        else None
    )
    total_rate = (
        None
        if sc_rate is None and export_rate is None
        else round((sc_rate or 0.0) + (export_rate or 0.0), 4)
    )

    return SavingsCurrent(
        timestamp=snapshot.timestamp,
        self_consumption_w=sc_w,
        export_w=export_w,
        savings_per_hour_eur=sc_rate,
        export_earnings_per_hour_eur=export_rate,
        total_benefit_per_hour_eur=total_rate,
        prices=prices,
    )


def _period_start_local(period: str, now_local: datetime) -> datetime | None:
    """Local start of a period; None for lifetime (= all stored data)."""
    midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return midnight
    if period == "week":
        return midnight - timedelta(days=now_local.weekday())
    if period == "month":
        return midnight.replace(day=1)
    return None  # lifetime


def _period_start_utc(now_local: datetime) -> dict[str, str]:
    """UTC ISO start timestamps for today / this week (Mon) / this month."""
    return {
        name: _period_start_local(key, now_local)
        .astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        for name, key in
        (("today", "today"), ("this_week", "week"), ("this_month", "month"))
    }


def compute_summary(config: AddonConfig, now: datetime | None = None) -> SavingsSummary:
    """Full savings summary from stored telemetry history."""
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    prices = _prices(config)
    starts = _period_start_utc(now_utc.astimezone())

    periods = {
        name: period_savings(database.get_snapshots_since(start), prices)
        for name, start in starts.items()
    }
    lifetime = period_savings(database.get_snapshots_since(None), prices)

    # Projections: refuse to extrapolate from less than MIN_OBSERVATION_DAYS.
    first_ts = database.get_first_snapshot_ts()
    avg_daily = None
    annual = None
    observed_days = 0.0
    if first_ts is not None:
        observed_days = (now_utc - datetime.fromisoformat(first_ts)).total_seconds() / 86400.0
        if observed_days >= MIN_OBSERVATION_DAYS:
            avg_daily = round(lifetime.total_benefit_eur / observed_days, 4)
            annual = round(avg_daily * 365.0, 2)
        else:
            logger.info(
                "Only %.2f days of telemetry - refusing annual projection", observed_days
            )

    payback = _payback_status(config, lifetime.total_benefit_eur, avg_daily, now_utc)

    return SavingsSummary(
        timestamp=now_utc.isoformat(timespec="seconds"),
        today=periods["today"],
        this_week=periods["this_week"],
        this_month=periods["this_month"],
        lifetime=lifetime,
        average_daily_benefit_eur=avg_daily,
        estimated_annual_savings_eur=annual,
        payback=payback,
        measured_since=first_ts,
        installation_date=config.installation_date or None,
        prices=prices,
    )


def compute_detail(config: AddonConfig, period: str, now: datetime | None = None) -> SavingsDetail:
    """Explainable savings for one period, with transparency warnings.

    Warnings emitted:
    - low_data_coverage:   usable data covers < 50 % of the elapsed period
    - default_tariff:      prices still equal the shipped defaults
    - no_system_cost:      system_cost_eur not configured (no payback possible)
    - no_payback_estimate: cost configured but < 1 day of history
    """
    if period not in DETAIL_PERIODS:
        raise ValueError(f"Unknown period {period!r}; valid: {DETAIL_PERIODS}")

    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    prices = _prices(config)

    start_local = _period_start_local(period, now_utc.astimezone())
    if start_local is not None:
        start_utc_iso = start_local.astimezone(timezone.utc).isoformat(timespec="seconds")
    else:
        start_utc_iso = database.get_first_snapshot_ts()  # lifetime; None when empty
    snapshots = database.get_snapshots_since(
        start_utc_iso if start_local is not None else None
    )
    savings = period_savings(snapshots, prices)

    elapsed_hours = None
    if start_utc_iso is not None:
        elapsed_hours = round(
            max((now_utc - datetime.fromisoformat(start_utc_iso)).total_seconds(), 0.0)
            / 3600.0,
            2,
        )
    coverage_percent = None
    if elapsed_hours is not None and elapsed_hours > 0:
        coverage_percent = round(
            min(savings.data_coverage_hours / elapsed_hours * 100.0, 100.0), 1
        )

    warnings: list[SavingsWarning] = []

    if start_utc_iso is None:
        warnings.append(SavingsWarning(
            code="low_data_coverage", severity="warning",
            message="No telemetry recorded yet — map your entities and let the "
                    "add-on run; numbers appear within minutes.",
        ))
    elif (
        elapsed_hours is not None
        and elapsed_hours >= MIN_ELAPSED_HOURS_FOR_COVERAGE_WARNING
        and (coverage_percent is None or coverage_percent < LOW_COVERAGE_PERCENT)
    ):
        warnings.append(SavingsWarning(
            code="low_data_coverage", severity="warning",
            message=f"Only {savings.data_coverage_hours:.1f} h of the last "
                    f"{elapsed_hours:.1f} h have telemetry "
                    f"({coverage_percent or 0:.0f} % coverage). Missing time is "
                    f"counted as zero savings, so the real value is likely higher.",
        ))

    tariff_is_default = (
        config.electricity_import_price_eur_per_kwh == DEFAULT_IMPORT_PRICE_EUR_PER_KWH
        and config.feed_in_tariff_eur_per_kwh == DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH
    )
    if tariff_is_default:
        warnings.append(SavingsWarning(
            code="default_tariff", severity="info",
            message="Calculations use the shipped default tariff "
                    f"(€ {DEFAULT_IMPORT_PRICE_EUR_PER_KWH:.2f}/kWh import, "
                    f"€ {DEFAULT_FEED_IN_TARIFF_EUR_PER_KWH:.2f}/kWh feed-in). "
                    "Set your real prices in the add-on options for accurate euros.",
        ))

    if config.system_cost_eur <= 0:
        warnings.append(SavingsWarning(
            code="no_system_cost", severity="info",
            message="system_cost_eur is not set — payback progress and payback "
                    "date cannot be calculated.",
        ))
    else:
        first_ts = database.get_first_snapshot_ts()
        observed_days = (
            (now_utc - datetime.fromisoformat(first_ts)).total_seconds() / 86400.0
            if first_ts is not None
            else 0.0
        )
        if observed_days < MIN_OBSERVATION_DAYS:
            warnings.append(SavingsWarning(
                code="no_payback_estimate", severity="info",
                message="Payback estimate unavailable: it needs at least 24 h of "
                        "telemetry history to compute a daily average. No number "
                        "is shown rather than a guess.",
            ))

    return SavingsDetail(
        period=period,
        period_start=start_utc_iso,
        period_end=now_utc.isoformat(timespec="seconds"),
        savings=savings,
        elapsed_hours=elapsed_hours,
        coverage_percent=coverage_percent,
        warnings=warnings,
        tariff_is_default=tariff_is_default,
        prices=prices,
        formulas=FORMULAS,
    )


def _payback_status(
    config: AddonConfig,
    recovered_eur: float,
    avg_daily_benefit: float | None,
    now_utc: datetime,
) -> PaybackStatus:
    """Payback progress against the configured system cost.

    progress = measured lifetime benefit / system_cost
    payback date = today + (system_cost - recovered) / avg_daily_benefit days

    Both are None when system_cost is not configured; the date is also None
    while there is not enough history for a daily average.
    """
    cost = config.system_cost_eur
    if cost <= 0:
        return PaybackStatus(
            system_cost_eur=0.0,
            recovered_eur=round(recovered_eur, 2),
            progress_percent=None,
            estimated_payback_date=None,
        )

    progress = min(recovered_eur / cost * 100.0, 100.0)
    payback_date = None
    if recovered_eur >= cost:
        payback_date = now_utc.date().isoformat()
    elif avg_daily_benefit is not None and avg_daily_benefit > 0:
        days_remaining = (cost - recovered_eur) / avg_daily_benefit
        payback_date = (now_utc + timedelta(days=days_remaining)).date().isoformat()

    return PaybackStatus(
        system_cost_eur=cost,
        recovered_eur=round(recovered_eur, 2),
        progress_percent=round(progress, 4),
        estimated_payback_date=payback_date,
    )
