"""Unit tests for add-on-native Home Assistant connection resolution.

Run from solar-brain-addon/:  python tests/test_ha_native.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def test_local_manual_token():
    os.environ.pop("SUPERVISOR_TOKEN", None)
    c = HomeAssistantClient(MANUAL)
    assert c.mode == "local" and c.auth == "manual_token", (c.mode, c.auth)
    assert c.is_configured
    assert c._base_url == "http://192.168.1.10:8123", c._base_url  # rstrip /
    assert c.connection_message == MSG_LOCAL, c.connection_message
    print("PASS local mode with manual token")


def test_local_not_configured():
    os.environ.pop("SUPERVISOR_TOKEN", None)
    c = HomeAssistantClient(EMPTY)
    assert c.mode == "local" and c.auth == "not_configured", (c.mode, c.auth)
    assert not c.is_configured
    assert c.connection_message == MSG_LOCAL
    print("PASS local mode not configured")


def test_addon_mode_supervisor_wins():
    os.environ["SUPERVISOR_TOKEN"] = "supervisor-secret"
    try:
        # Even with manual url/token present, the Supervisor must win.
        c = HomeAssistantClient(MANUAL)
        assert c.mode == "addon" and c.auth == "supervisor_token", (c.mode, c.auth)
        assert c.is_configured
        assert c._base_url == SUPERVISOR_CORE_URL, c._base_url
        assert c._token == "supervisor-secret"
        assert c.connection_message == MSG_ADDON, c.connection_message

        # And of course with no manual config at all.
        c2 = HomeAssistantClient(EMPTY)
        assert c2.mode == "addon" and c2.auth == "supervisor_token"
        assert c2.is_configured
    finally:
        os.environ.pop("SUPERVISOR_TOKEN", None)
    print("PASS add-on mode: supervisor token wins, zero config needed")


def test_status_messages():
    """Reachability-aware copy: non-technical reconnect message in add-on mode."""
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
        os.environ.pop("SUPERVISOR_TOKEN", None)

    local = HomeAssistantClient(MANUAL)
    assert local.status_message(True) == MSG_LOCAL
    assert local.status_message(False) == MSG_LOCAL
    print("PASS reachability-aware status messages")


if __name__ == "__main__":
    test_local_manual_token()
    test_local_not_configured()
    test_addon_mode_supervisor_wins()
    test_status_messages()
    print("\nALL HA-NATIVE TESTS PASSED")
