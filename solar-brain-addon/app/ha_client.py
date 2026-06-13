"""Home Assistant REST API client - add-on native.

Connection resolution, in priority order:

1. **Add-on mode**: the Supervisor injects a token (``SUPERVISOR_TOKEN`` on
   current Supervisors, ``HASSIO_TOKEN`` on older ones) because config.yaml
   sets ``homeassistant_api: true``. We reach Home Assistant through the
   Supervisor proxy at ``http://supervisor/core/api``. No user config at all.
2. **Local dev mode** with HOME_ASSISTANT_URL + HOME_ASSISTANT_TOKEN env
   vars (a long-lived access token) - for debugging outside HA only.
3. **Not configured**: telemetry endpoints return 503 with guidance.

Read-only helpers only - no hardware control.
"""

import logging
import os

import httpx

from .models import AddonConfig

logger = logging.getLogger("solar_brain.ha")

SUPERVISOR_CORE_URL = "http://supervisor/core"

MSG_ADDON = "Connected via Home Assistant Supervisor."
MSG_ADDON_RECONNECTING = (
    "Home Assistant is temporarily unavailable. "
    "Solar Brain will reconnect automatically."
)
MSG_LOCAL = "Home Assistant connection requires local dev token."


class HomeAssistantClient:
    def __init__(self, config: AddonConfig):
        # Capture token presence for startup diagnostics (never the values).
        self.supervisor_token_present = bool(os.getenv("SUPERVISOR_TOKEN"))
        self.hassio_token_present = bool(os.getenv("HASSIO_TOKEN"))

        # Accept either token name: SUPERVISOR_TOKEN (current) or the legacy
        # HASSIO_TOKEN (older Supervisor versions inject only this one).
        supervisor_token = os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN") or ""

        if supervisor_token:
            # Inside the add-on the Supervisor always wins; manual URL/token
            # are deliberately ignored (they are a local-dev facility).
            self.mode = "addon"
            self.auth = "supervisor"
            self.token_source = (
                "SUPERVISOR_TOKEN" if self.supervisor_token_present else "HASSIO_TOKEN"
            )
            self._base_url = SUPERVISOR_CORE_URL
            self._token = supervisor_token
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

    async def log_startup_diagnostics(self) -> bool:
        """Log exactly how HA access was resolved, and whether it responds.

        Returns the live reachability result. Logs token *presence* only -
        never the secret values.
        """
        logger.info(
            "HA detect: SUPERVISOR_TOKEN present=%s, HASSIO_TOKEN present=%s",
            self.supervisor_token_present,
            self.hassio_token_present,
        )
        logger.info(
            "HA detect: mode=%s auth=%s token_source=%s base_url=%s",
            self.mode,
            self.auth,
            self.token_source,
            self.base_url or "(none)",
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
