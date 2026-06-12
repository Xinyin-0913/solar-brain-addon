"""Unit tests for the Savings Engine V1.

Run from solar-brain-addon/:  python tests/test_savings.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_savings_")

from app import database  # noqa: E402
from app.models import AddonConfig, SavingsPrices, TelemetrySnapshot  # noqa: E402
from app.savings import (  # noqa: E402
    _payback_status,
    compute_summary,
    current_savings,
    integrate_energy,
    period_savings,
)

BASE = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)
PRICES = SavingsPrices(import_eur_per_kwh=0.30, feed_in_eur_per_kwh=0.08)


def ts(offset_seconds: float) -> str:
    return (BASE + timedelta(seconds=offset_seconds)).isoformat(timespec="seconds")


def snap(offset_s: float, solar=None, load=None, export=None) -> dict:
    return {"ts": ts(offset_s), "solar_power_w": solar, "home_load_w": load,
            "grid_export_w": export}


def approx(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) < eps


def test_integration_exact():
    """61 snapshots @60s, constant power -> exact energies over 1 h."""
    snaps = [snap(i * 60, solar=3000, load=1500, export=1200) for i in range(61)]
    e = integrate_energy(snaps)
    assert approx(e["self_consumption_kwh"], 1.5), e   # min(3000,1500)=1500 W x 1 h
    assert approx(e["export_kwh"], 1.2), e
    assert approx(e["solar_kwh"], 3.0), e
    assert approx(e["covered_hours"], 1.0), e
    print("PASS integration: exact energy over 1 h")


def test_gap_capping():
    """A 2 h gap only credits MAX_GAP_SECONDS (300 s) of energy."""
    snaps = [snap(0, solar=1000, load=1000), snap(7200, solar=1000, load=1000)]
    e = integrate_energy(snaps)
    assert approx(e["self_consumption_kwh"], 1000 * 300 / 3.6e6), e  # 0.08333 kWh
    assert approx(e["covered_hours"], 300 / 3600), e
    print("PASS integration: gap capped at 300 s")


def test_missing_values():
    """Missing load skips self-consumption for that interval, keeps solar."""
    snaps = [
        snap(0, solar=2000, load=1000, export=0),
        snap(60, solar=2000, load=None, export=0),
        snap(120, solar=2000, load=1000, export=0),
    ]
    e = integrate_energy(snaps)
    assert approx(e["self_consumption_kwh"], 1000 * 60 / 3.6e6), e  # 1st interval only
    assert approx(e["solar_kwh"], 2000 * 120 / 3.6e6), e            # both intervals
    print("PASS integration: missing values never invent energy")


def test_negative_clamp():
    """Negative powers (signed sensors, standby draw) clamp to 0."""
    snaps = [snap(0, solar=-50, load=500, export=-100), snap(60, solar=-50, load=500, export=-100)]
    e = integrate_energy(snaps)
    assert e["self_consumption_kwh"] == 0.0, e
    assert e["export_kwh"] == 0.0, e
    assert e["solar_kwh"] == 0.0, e
    print("PASS integration: negative powers clamped")


def test_period_money():
    """kWh x tariff: 1.5 kWh x 0.30 + 1.2 kWh x 0.08 = 0.546 EUR."""
    snaps = [snap(i * 60, solar=3000, load=1500, export=1200) for i in range(61)]
    p = period_savings(snaps, PRICES)
    assert approx(p.self_consumption_savings_eur, 0.45, 1e-4), p
    assert approx(p.export_earnings_eur, 0.096, 1e-4), p
    assert approx(p.total_benefit_eur, 0.546, 1e-4), p
    print("PASS period: money matches energy x tariff")


def test_current_rates():
    config = AddonConfig(electricity_import_price_eur_per_kwh=0.32,
                         feed_in_tariff_eur_per_kwh=0.08)
    s = TelemetrySnapshot(timestamp=ts(0), solar_power_w=4310, home_load_w=1620,
                          grid_export_w=1640)
    c = current_savings(s, config)
    assert c.self_consumption_w == 1620, c     # min(4310, 1620)
    assert c.export_w == 1640, c
    assert approx(c.savings_per_hour_eur, 1.620 * 0.32, 1e-4), c       # 0.5184
    assert approx(c.export_earnings_per_hour_eur, 1.640 * 0.08, 1e-4)  # 0.1312
    assert approx(c.total_benefit_per_hour_eur, 0.6496, 1e-4), c

    # None propagation: no solar value -> no self-consumption claim.
    s2 = TelemetrySnapshot(timestamp=ts(0), solar_power_w=None, home_load_w=1620,
                           grid_export_w=500)
    c2 = current_savings(s2, config)
    assert c2.self_consumption_w is None and c2.savings_per_hour_eur is None, c2
    assert approx(c2.total_benefit_per_hour_eur, 0.04, 1e-4), c2  # export only
    print("PASS current: instantaneous rates")


def test_payback():
    now = BASE
    config = AddonConfig(system_cost_eur=10000.0)
    p = _payback_status(config, recovered_eur=500.0, avg_daily_benefit=2.5, now_utc=now)
    assert approx(p.progress_percent, 5.0), p
    expected = (now + timedelta(days=(10000 - 500) / 2.5)).date().isoformat()
    assert p.estimated_payback_date == expected, p

    # No system cost configured -> no payback claims.
    p2 = _payback_status(AddonConfig(), 500.0, 2.5, now)
    assert p2.progress_percent is None and p2.estimated_payback_date is None, p2

    # Already paid back -> 100 %, date = today.
    p3 = _payback_status(config, 12000.0, 2.5, now)
    assert p3.progress_percent == 100.0, p3
    assert p3.estimated_payback_date == now.date().isoformat(), p3
    print("PASS payback: progress and date")


def test_summary_with_db():
    """End-to-end against SQLite: period boundaries and projections."""
    database.init_db()
    now = datetime.now(timezone.utc)

    def insert(when: datetime, solar, load, export):
        database.insert_snapshot(TelemetrySnapshot(
            timestamp=when.isoformat(timespec="seconds"),
            solar_power_w=solar, home_load_w=load, grid_export_w=export))

    # 30 h ago (yesterday): one 60 s interval at sc=1000 W.
    old = now - timedelta(hours=30)
    insert(old, 2000, 1000, 0)
    insert(old + timedelta(seconds=60), 2000, 1000, 0)
    # 2 minutes ago (today): one 60 s interval at sc=1000 W.
    insert(now - timedelta(seconds=120), 3000, 1000, 0)
    insert(now - timedelta(seconds=60), 3000, 1000, 0)

    config = AddonConfig(electricity_import_price_eur_per_kwh=0.30,
                         system_cost_eur=8000.0)
    s = compute_summary(config, now=now)

    one_interval_eur = 1000 * 60 / 3.6e6 * 0.30   # 0.005 EUR
    gap_credit_eur = 1000 * 300 / 3.6e6 * 0.30    # 0.025 EUR: the 30 h gap
    # still credits MAX_GAP_SECONDS of the last-known power (documented rule)
    assert approx(s.today.total_benefit_eur, one_interval_eur, 1e-4), s.today
    assert approx(s.lifetime.total_benefit_eur,
                  2 * one_interval_eur + gap_credit_eur, 1e-4), s.lifetime
    assert s.this_week.total_benefit_eur >= s.today.total_benefit_eur, s
    assert s.lifetime.total_benefit_eur >= s.this_week.total_benefit_eur, s
    assert s.measured_since is not None
    # 30 h of history >= 1 day -> projections must exist and be consistent.
    assert s.average_daily_benefit_eur is not None and s.average_daily_benefit_eur > 0
    assert s.estimated_annual_savings_eur is not None
    assert approx(s.estimated_annual_savings_eur,
                  round(s.average_daily_benefit_eur * 365, 2), 0.01)
    assert s.payback.progress_percent is not None and s.payback.progress_percent > 0
    assert s.payback.estimated_payback_date is not None
    print("PASS summary: SQLite periods, projections, payback")


def test_empty_db_refuses_projections():
    """Fresh install: zeros for periods, None for every projection."""
    os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_empty_")
    import importlib
    importlib.reload(database)
    database.init_db()
    s = compute_summary(AddonConfig(system_cost_eur=8000.0))
    assert s.lifetime.total_benefit_eur == 0.0, s
    assert s.average_daily_benefit_eur is None, s
    assert s.estimated_annual_savings_eur is None, s
    assert s.payback.estimated_payback_date is None, s
    assert s.payback.progress_percent == 0.0, s
    assert s.measured_since is None, s
    print("PASS summary: empty history -> zeros and None, never guesses")


if __name__ == "__main__":
    test_integration_exact()
    test_gap_capping()
    test_missing_values()
    test_negative_clamp()
    test_period_money()
    test_current_rates()
    test_payback()
    test_summary_with_db()
    test_empty_db_refuses_projections()
    print("\nALL SAVINGS TESTS PASSED")
