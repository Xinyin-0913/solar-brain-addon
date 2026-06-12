"""Unit tests for Savings Explainability (compute_detail + warnings).

Run from solar-brain-addon/:  python tests/test_savings_detail.py
"""

import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_detail_")

from app import database  # noqa: E402
from app.models import AddonConfig, TelemetrySnapshot  # noqa: E402
from app.savings import compute_detail  # noqa: E402

BASE = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)


def fresh_db() -> None:
    os.environ["SOLAR_BRAIN_DATA_DIR"] = tempfile.mkdtemp(prefix="solar_brain_detail_")
    importlib.reload(database)
    database.init_db()


def insert(when: datetime, solar=2000.0, load=1000.0, export=0.0) -> None:
    database.insert_snapshot(TelemetrySnapshot(
        timestamp=when.astimezone(timezone.utc).isoformat(timespec="seconds"),
        solar_power_w=solar, home_load_w=load, grid_export_w=export))


def codes(detail) -> list[str]:
    return [w.code for w in detail.warnings]


CFG_DEFAULT = AddonConfig()  # shipped tariff defaults, no system cost
CFG_CUSTOM = AddonConfig(electricity_import_price_eur_per_kwh=0.32,
                         feed_in_tariff_eur_per_kwh=0.082,
                         system_cost_eur=8000.0)


def test_period_selection():
    """today excludes older data; lifetime includes everything."""
    fresh_db()
    now = datetime.now(timezone.utc)
    old = now - timedelta(hours=30)
    insert(old)
    insert(old + timedelta(seconds=60))
    insert(now - timedelta(seconds=120))
    insert(now - timedelta(seconds=60))

    one_interval = 1000 * 60 / 3.6e6 * 0.30   # 0.005 EUR
    gap_credit = 1000 * 300 / 3.6e6 * 0.30    # 0.025 EUR

    d_today = compute_detail(CFG_DEFAULT, "today", now=now)
    assert d_today.period == "today", d_today
    assert abs(d_today.savings.total_benefit_eur - one_interval) < 1e-4, d_today.savings

    # period_start must be local midnight, expressed in UTC.
    midnight_utc = (now.astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                    .astimezone(timezone.utc).isoformat(timespec="seconds"))
    assert d_today.period_start == midnight_utc, d_today.period_start

    d_life = compute_detail(CFG_DEFAULT, "lifetime", now=now)
    assert abs(d_life.savings.total_benefit_eur - (2 * one_interval + gap_credit)) < 1e-4
    assert d_life.period_start == database.get_first_snapshot_ts(), d_life

    for period in ("week", "month"):
        d = compute_detail(CFG_DEFAULT, period, now=now)
        assert d.savings.total_benefit_eur >= d_today.savings.total_benefit_eur, d

    try:
        compute_detail(CFG_DEFAULT, "year")
        raise AssertionError("invalid period must raise")
    except ValueError:
        pass
    print("PASS period selection (incl. invalid period rejected)")


def test_low_coverage_warning():
    fresh_db()
    insert(BASE)
    insert(BASE + timedelta(seconds=60))
    insert(BASE + timedelta(seconds=120))

    # 2 min of data in a 30 h window -> warning.
    d = compute_detail(CFG_DEFAULT, "lifetime", now=BASE + timedelta(hours=30))
    assert "low_data_coverage" in codes(d), d.warnings
    assert d.coverage_percent is not None and d.coverage_percent < 1.0, d

    # Elapsed under 1 h -> too early to judge, no coverage warning.
    d2 = compute_detail(CFG_DEFAULT, "lifetime", now=BASE + timedelta(seconds=130))
    assert "low_data_coverage" not in codes(d2), d2.warnings

    # Dense data (every 60 s for 1 h) -> high coverage, no warning.
    fresh_db()
    for i in range(61):
        insert(BASE + timedelta(seconds=60 * i))
    d3 = compute_detail(CFG_DEFAULT, "lifetime", now=BASE + timedelta(seconds=3660))
    assert d3.coverage_percent is not None and d3.coverage_percent > 90, d3
    assert "low_data_coverage" not in codes(d3), d3.warnings

    # Empty database -> explicit "no telemetry" coverage warning.
    fresh_db()
    d4 = compute_detail(CFG_DEFAULT, "lifetime", now=BASE)
    assert "low_data_coverage" in codes(d4), d4.warnings
    assert d4.period_start is None, d4
    print("PASS low data coverage warning (sparse / early / dense / empty)")


def test_default_tariff_warning():
    fresh_db()
    insert(BASE)
    insert(BASE + timedelta(seconds=60))

    d = compute_detail(CFG_DEFAULT, "lifetime", now=BASE + timedelta(seconds=120))
    assert d.tariff_is_default is True, d
    assert "default_tariff" in codes(d), d.warnings

    d2 = compute_detail(CFG_CUSTOM, "lifetime", now=BASE + timedelta(seconds=120))
    assert d2.tariff_is_default is False, d2
    assert "default_tariff" not in codes(d2), d2.warnings
    print("PASS default tariff warning")


def test_system_cost_and_payback_warnings():
    fresh_db()
    insert(BASE)
    insert(BASE + timedelta(seconds=60))

    # No system cost -> no_system_cost; payback warning not also stacked.
    d = compute_detail(CFG_DEFAULT, "today", now=BASE + timedelta(seconds=120))
    assert "no_system_cost" in codes(d), d.warnings
    assert "no_payback_estimate" not in codes(d), d.warnings

    # Cost configured but < 24 h history -> no_payback_estimate instead.
    d2 = compute_detail(CFG_CUSTOM, "today", now=BASE + timedelta(seconds=120))
    assert "no_system_cost" not in codes(d2), d2.warnings
    assert "no_payback_estimate" in codes(d2), d2.warnings

    # Cost configured and >= 24 h history -> neither warning.
    insert(BASE + timedelta(hours=26))
    d3 = compute_detail(CFG_CUSTOM, "today", now=BASE + timedelta(hours=26, seconds=60))
    assert "no_system_cost" not in codes(d3), d3.warnings
    assert "no_payback_estimate" not in codes(d3), d3.warnings
    print("PASS system cost & payback availability warnings")


if __name__ == "__main__":
    test_period_selection()
    test_low_coverage_warning()
    test_default_tariff_warning()
    test_system_cost_and_payback_warnings()
    print("\nALL SAVINGS DETAIL TESTS PASSED")
