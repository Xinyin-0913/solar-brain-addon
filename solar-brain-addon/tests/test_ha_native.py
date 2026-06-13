"""Unit tests for add-on-native Home Assistant connection resolution.

Covers the three runtime modes plus the legacy-token fallback:
- supervisor token mode  (SUPERVISOR_TOKEN)
- supervisor token mode  (legacy HASSIO_TOKEN fallback)
- local dev token mode   (HOME_ASSISTANT_URL + HOME_ASSISTANT_TOKEN)
- no token offline mode

Run from solar-brain-addon/:  python tests/test_ha_native.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import ha_client as ha
from app.ha_client import (
    MSG_ADDON,
    MSG_ADDON_RECONNECTING,
    MSG_LOCAL,
    SUPERVISOR_CORE_URL,
    HomeAssistantClient,
)
from app.models import AddonConfig

MANUAL = AddonConfig(home_assistant_url="http://192.168.1.10:8123/",
                     home_assistant_token="dev-token")
EMPTY = AddonConfig()


def clear_supervisor_env() -> None:
    """Both token names must be cleared - either triggers add-on mode."""
    os.environ.pop("SUPERVISOR_TOKEN", None)
    os.environ.pop("HASSIO_TOKEN", None)


def test_supervisor_token_mode():
    clear_supervisor_env()
    os.environ["SUPERVISOR_TOKEN"] = "supervisor-secret"
    try:
        # Even with manual url/token present, the Supervisor must win.
        c = HomeAssistantClient(MANUAL)
        assert c.mode == "addon" and c.auth == "supervisor", (c.mode, c.auth)
        assert c.token_source == "SUPERVISOR_TOKEN", c.token_source
        assert c.is_configured
        assert c._base_url == SUPERVISOR_CORE_URL, c._base_url
        assert c.base_url == "http://supervisor/core/api", c.base_url
        assert c._token == "supervisor-secret"
        assert c.connection_message == MSG_ADDON, c.connection_message

        # And with no manual config at all (the real add-on case).
        c2 = HomeAssistantClient(EMPTY)
        assert c2.mode == "addon" and c2.auth == "supervisor"
        assert c2.is_configured
    finally:
        clear_supervisor_env()
    print("PASS supervisor token mode (SUPERVISOR_TOKEN, zero config)")


def test_legacy_hassio_token_fallback():
    """Older Supervisors inject HASSIO_TOKEN only - must still be add-on mode."""
    clear_supervisor_env()
    os.environ["HASSIO_TOKEN"] = "legacy-secret"
    try:
        c = HomeAssistantClient(EMPTY)
        assert c.mode == "addon" and c.auth == "supervisor", (c.mode, c.auth)
        assert c.token_source == "HASSIO_TOKEN", c.token_source
        assert c.is_configured
        assert c._base_url == SUPERVISOR_CORE_URL, c._base_url
        assert c._token == "legacy-secret"
    finally:
        clear_supervisor_env()
    print("PASS legacy HASSIO_TOKEN fallback -> add-on mode")


def test_s6_container_environment_fallback():
    """Token only in the s6 container-environment file (the real add-on case)."""
    clear_supervisor_env()
    tmp = Path(tempfile.mkdtemp(prefix="s6_env_"))
    (tmp / "SUPERVISOR_TOKEN").write_text("token-from-s6-file\n")
    original = ha.S6_ENV_DIRS
    ha.S6_ENV_DIRS = (str(tmp),)
    try:
        c = HomeAssistantClient(EMPTY)
        assert c.mode == "addon" and c.auth == "supervisor", (c.mode, c.auth)
        assert c.token_source == "SUPERVISOR_TOKEN (s6 file)", c.token_source
        assert c._token == "token-from-s6-file", c._token
        assert c.is_configured
        # Diagnostics expose the dir + file NAME, never the value.
        diag = c.safe_runtime_diagnostics()
        assert str(tmp) in diag["s6_container_environment"], diag
        assert "SUPERVISOR_TOKEN" in diag["s6_container_environment"][str(tmp)]
        assert "token-from-s6-file" not in repr(diag), "diagnostics leaked a token value"
    finally:
        ha.S6_ENV_DIRS = original
        clear_supervisor_env()
    print("PASS s6 container_environment file fallback")


def test_env_var_wins_over_s6_file():
    """A real env var takes precedence over the s6 file."""
    clear_supervisor_env()
    tmp = Path(tempfile.mkdtemp(prefix="s6_env_"))
    (tmp / "SUPERVISOR_TOKEN").write_text("file-token")
    os.environ["SUPERVISOR_TOKEN"] = "env-token"
    original = ha.S6_ENV_DIRS
    ha.S6_ENV_DIRS = (str(tmp),)
    try:
        c = HomeAssistantClient(EMPTY)
        assert c.token_source == "SUPERVISOR_TOKEN", c.token_source
        assert c._token == "env-token", c._token
    finally:
        ha.S6_ENV_DIRS = original
        clear_supervisor_env()
    print("PASS env var precedence over s6 file")


def test_local_dev_token_mode():
    clear_supervisor_env()
    c = HomeAssistantClient(MANUAL)
    assert c.mode == "local" and c.auth == "manual_token", (c.mode, c.auth)
    assert c.token_source == "HOME_ASSISTANT_TOKEN", c.token_source
    assert c.is_configured
    assert c._base_url == "http://192.168.1.10:8123", c._base_url  # rstrip /
    assert c.base_url == "http://192.168.1.10:8123/api", c.base_url
    assert c.connection_message == MSG_LOCAL, c.connection_message
    print("PASS local dev token mode")


def test_no_token_offline_mode():
    clear_supervisor_env()
    c = HomeAssistantClient(EMPTY)
    assert c.mode == "local" and c.auth == "not_configured", (c.mode, c.auth)
    assert c.token_source == "none", c.token_source
    assert not c.is_configured
    assert c.base_url == "", c.base_url
    assert c.connection_message == MSG_LOCAL
    # Offline: ping is a clean False, never an exception.
    assert asyncio.run(c.ping()) is False
    print("PASS no token offline mode")


def test_status_messages():
    """Reachability-aware copy: non-technical reconnect message in add-on mode."""
    clear_supervisor_env()
    os.environ["SUPERVISOR_TOKEN"] = "abc"
    try:
        addon = HomeAssistantClient(EMPTY)
        assert addon.status_message(True) == MSG_ADDON
        assert addon.status_message(False) == MSG_ADDON_RECONNECTING
        # Non-technical: no jargon a normal user would trip over.
        for term in ("API", "token", "supervisor", "503", "env"):
            assert term.lower() not in MSG_ADDON_RECONNECTING.lower(), term
        assert "automatically" in MSG_ADDON_RECONNECTING
    finally:
        clear_supervisor_env()

    local = HomeAssistantClient(MANUAL)
    assert local.status_message(True) == MSG_LOCAL
    assert local.status_message(False) == MSG_LOCAL
    print("PASS reachability-aware status messages")


if __name__ == "__main__":
    test_supervisor_token_mode()
    test_legacy_hassio_token_fallback()
    test_s6_container_environment_fallback()
    test_env_var_wins_over_s6_file()
    test_local_dev_token_mode()
    test_no_token_offline_mode()
    test_status_messages()
    print("\nALL HA-NATIVE TESTS PASSED")
