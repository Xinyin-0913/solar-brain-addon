"""Backward compatibility: legacy options.json files must never break startup.

Pre-0.5.0 installs have home_assistant_url / home_assistant_token in
/data/options.json (the Supervisor does not delete removed options), and
future versions may add keys old code has never seen. Both must load safely.

Run from solar-brain-addon/:  python tests/test_backcompat.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import models
from app.ha_client import SUPERVISOR_CORE_URL, HomeAssistantClient
from app.models import AddonConfig

LEGACY_OPTIONS = {
    # Options removed in 0.5.0 but still present in old installs:
    "home_assistant_url": "http://homeassistant.local:8123",
    "home_assistant_token": "legacy-long-lived-token",
    # Current options:
    "latitude": 52.52,
    "longitude": 13.405,
    "electricity_import_price_eur_per_kwh": 0.32,
    "feed_in_tariff_eur_per_kwh": 0.08,
    "system_cost_eur": 8000.0,
    "installation_date": "2025-04-09",
    "openrouter_api_key": "",
    "enable_ai": False,
    # A key this version has never heard of:
    "some_future_unknown_option": {"nested": True},
}


def test_legacy_options_load_safely():
    options_file = Path(tempfile.mkdtemp(prefix="solar_brain_compat_")) / "options.json"
    options_file.write_text(json.dumps(LEGACY_OPTIONS))
    original = models.OPTIONS_FILE
    models.OPTIONS_FILE = options_file
    try:
        config = AddonConfig.load()
        # Known options loaded; unknown key ignored without error.
        assert config.latitude == 52.52, config
        assert config.electricity_import_price_eur_per_kwh == 0.32, config
        assert config.system_cost_eur == 8000.0, config
        # Legacy fields still parse (model keeps them for local dev).
        assert config.home_assistant_url == "http://homeassistant.local:8123"
    finally:
        models.OPTIONS_FILE = original
    print("PASS legacy + unknown options.json keys load safely")
    return config


def test_supervisor_still_wins_over_legacy(config: AddonConfig):
    """An upgraded add-on install: legacy token present AND supervisor token."""
    os.environ["SUPERVISOR_TOKEN"] = "supervisor-secret"
    try:
        client = HomeAssistantClient(config)
        assert client.mode == "addon", client.mode
        assert client.auth == "supervisor_token", client.auth
        assert client._base_url == SUPERVISOR_CORE_URL, client._base_url
        assert client._token == "supervisor-secret"
    finally:
        os.environ.pop("SUPERVISOR_TOKEN", None)
    print("PASS supervisor token wins over legacy options after upgrade")


def test_unknown_constructor_kwargs_ignored():
    config = AddonConfig(latitude=1.0, totally_unknown_field="x")
    assert config.latitude == 1.0
    assert not hasattr(config, "totally_unknown_field")
    print("PASS unknown constructor kwargs ignored (pydantic extra=ignore)")


if __name__ == "__main__":
    cfg = test_legacy_options_load_safely()
    test_supervisor_still_wins_over_legacy(cfg)
    test_unknown_constructor_kwargs_ignored()
    print("\nALL BACKCOMPAT TESTS PASSED")
