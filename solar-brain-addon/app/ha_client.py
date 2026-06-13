"""Home Assistant REST API client - add-on native.

Connection resolution, in priority order:

1. **Add-on mode**: the Supervisor provides a token under ``SUPERVISOR_TOKEN``
   (current) or ``HASSIO_TOKEN`` (legacy). On the HA base images, s6-overlay
   captures the container environment into files and does NOT re-export it to
   our process, so the token is read from the environment first and then from
   the s6 container-environment files as a fallback. We reach Home Assistant
   through the Supervisor proxy at ``http://supervisor/core/api``. No user
   config at all.
2. **Local dev mode** with HOME_ASSISTANT_URL + HOME_ASSISTANT_TOKEN env
   vars (a long-lived access token) - for debugging outside HA only.
3. **Not configured**: telemetry endpoints return 503 with guidance.

Read-only helpers only - no hardware control.
"""

import json
import logging
import os
from pathlib import Path

import httpx

from .models import OPTIONS_FILE, AddonConfig

logger = logging.getLogger("solar_brain.ha")

SUPERVISOR_CORE_URL = "http://supervisor/core"

# Token env var names the Supervisor may use, in preference order.
TOKEN_ENV_VARS = ("SUPERVISOR_TOKEN", "HASSIO_TOKEN")

# s6-overlay stores the container environment here (v3 uses /run, v2 /var/run).
# The token is set on the container by the Supervisor but only lives in these
# files unless the process is launched with-contenv - so we read them directly.
S6_ENV_DIRS = (
    "/run/s6/container_environment",
    "/var/run/s6/container_environment",
)

MSG_ADDON = "Connected via Home Assistant Supervisor."
MSG_ADDON_RECONNECTING = (
    "Home Assistant is temporarily unavailable. "
    "Solar Brain will reconnect automatically."
)
MSG_LOCAL = "Home Assistant connection requires local dev token."


def _read_s6_env(name: str) -> str:
    """Read one container-environment variable from the s6 files, or ''."""
    for directory in S6_ENV_DIRS:
        path = Path(directory) / name
        try:
            if path.is_file():
                value = path.read_text().strip()
                if value:
                    return value
        except OSError:
            continue
    return ""


def _resolve_supervisor_token() -> tuple[str, str]:
    """Find the Supervisor token. Returns (token, source) or ('', '')."""
    for name in TOKEN_ENV_VARS:
        value = os.getenv(name)
        if value:
            return value, name
    for name in TOKEN_ENV_VARS:
        value = _read_s6_env(name)
        if value:
            return value, f"{name} (s6 file)"
    return "", ""


class HomeAssistantClient:
    def __init__(self, config: AddonConfig):
        token, source = _resolve_supervisor_token()

        if token:
            # Inside the add-on the Supervisor always wins; manual URL/token
            # are deliberately ignored (they are a local-dev facility).
            self.mode = "addon"
            self.auth = "supervisor"
            self.token_source = source
            self._base_url = SUPERVISOR_CORE_URL
            self._token = token
        elif config.home_assistant_url and config.home_assistant_token:
            self.mode = "local"
            self.auth = "manual_token"
            self.token_source = "HOME_ASSISTANT_TOKEN"
            self._base_url = config.home_assistant_url.rstrip("/")
            self._token = config.home_assistant_token
        else:
            self.mode = "local"
            self.auth = "not_configured"
            self.token_source = "none"
            self._base_url = ""
            self._token = ""

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url and self._token)

    @property
    def base_url(self) -> str:
        """HA REST API base, e.g. http://supervisor/core/api (empty if none)."""
        return f"{self._base_url}/api" if self._base_url else ""

    def safe_runtime_diagnostics(self) -> dict:
        """Diagnostics for logging and /api/debug/runtime.

        Contains NO secret values - only names, presence flags, and the
        already-public mode/auth/base_url. Safe to expose and to log.
        """
        # Env var NAMES (never values) that hint at HA/Supervisor tokens.
        env_keys = sorted(
            k for k in os.environ
            if any(s in k.upper() for s in ("TOKEN", "HASSIO", "SUPERVISOR"))
        )
        s6_dirs: dict[str, list[str]] = {}
        for directory in S6_ENV_DIRS:
            try:
                if os.path.isdir(directory):
                    s6_dirs[directory] = sorted(os.listdir(directory))
            except OSError:
                continue
        options = {"path": str(OPTIONS_FILE), "exists": OPTIONS_FILE.exists()}
        if OPTIONS_FILE.exists():
            try:
                options["keys"] = sorted(json.loads(OPTIONS_FILE.read_text()).keys())
            except (OSError, ValueError):
                options["keys"] = "unreadable"
        return {
            "mode": self.mode,
            "auth": self.auth,
            "token_source": self.token_source,
            "base_url": self.base_url,
            "token_present": self.is_configured,
            "env_keys_matching": env_keys,        # names only
            "s6_container_environment": s6_dirs,  # dir -> [var names]
            "options_json": options,              # path/exists/key names only
        }

    async def log_startup_diagnostics(self) -> bool:
        """Log exactly how HA access was resolved, and whether it responds.

        Returns the live reachability result. Logs token *presence* and key
        *names* only - never the secret values.
        """
        diag = self.safe_runtime_diagnostics()
        logger.info(
            "HA detect: mode=%s auth=%s token_source=%s base_url=%s token_present=%s",
            diag["mode"], diag["auth"], diag["token_source"],
            diag["base_url"] or "(none)", diag["token_present"],
        )
        logger.info(
            "HA detect: env keys matching TOKEN/HASSIO/SUPERVISOR: %s",
            diag["env_keys_matching"] or "(none)",
        )
        logger.info(
            "HA detect: s6 container_environment: %s",
            diag["s6_container_environment"] or "(no s6 env dir found)",
        )
        logger.info(
            "HA detect: /data/options.json exists=%s keys=%s",
            diag["options_json"]["exists"], diag["options_json"].get("keys", "n/a"),
        )
        if not self.is_configured:
            logger.warning(
                "HA detect: no API access configured - /api/entities/discover "
                "and /api/telemetry/current will return 503"
            )
            return False
        reachable = await self.ping()
        if reachable:
            logger.info("HA detect: API ping to %s/ succeeded", self.base_url)
        else:
            logger.warning(
                "HA detect: API ping to %s/ FAILED (Home Assistant may still "
                "be starting; will retry on each request)",
                self.base_url,
            )
        return reachable

    @property
    def connection_message(self) -> str:
        """User-facing copy for the current connection mode."""
        return MSG_ADDON if self.mode == "addon" else MSG_LOCAL

    def status_message(self, reachable: bool) -> str:
        """Connection copy that accounts for live reachability.

        In add-on mode an outage is normal (HA restarting) - the message
        stays non-technical and promises automatic reconnection.
        """
        if self.mode == "addon":
            return MSG_ADDON if reachable else MSG_ADDON_RECONNECTING
        return MSG_LOCAL

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def ping(self) -> bool:
        """Return True if the Home Assistant API is reachable."""
        if not self.is_configured:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self._base_url}/api/", headers=self._headers()
                )
                return response.status_code == 200
        except httpx.HTTPError as err:
            logger.warning("Home Assistant API not reachable: %s", err)
            return False

    async def get_states(self) -> list[dict] | None:
        """Fetch all entity states, or None when unreachable/not configured."""
        if not self.is_configured:
            logger.debug("HA client not configured, skipping get_states()")
            return None
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{self._base_url}/api/states", headers=self._headers()
                )
                response.raise_for_status()
                states = response.json()
                logger.debug("Fetched %d entity states from HA", len(states))
                return states
        except httpx.HTTPError as err:
            logger.warning("Failed to fetch states from Home Assistant: %s", err)
            return None

    async def get_state(self, entity_id: str) -> dict | None:
        """Fetch the state of a single entity, or None on failure."""
        if not self.is_configured:
            logger.debug("HA client not configured, skipping get_state(%s)", entity_id)
            return None
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self._base_url}/api/states/{entity_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as err:
            logger.warning("Failed to fetch state for %s: %s", entity_id, err)
            return None
