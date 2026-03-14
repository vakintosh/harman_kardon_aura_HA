"""Config flow for HK Aura Plus integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DEFAULT_PORT, DOMAIN, CONF_MEDIA_PLAYER_ENTITY

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MEDIA_PLAYER_ENTITY): str,
    }
)


class HKAuraPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HK Aura Plus."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            # Prevent duplicate entries for the same host:port
            self._async_abort_entries_match(
                {CONF_HOST: host, CONF_PORT: port}
            )

            # Test connection
            if await self._test_connection(host, port):
                return self.async_create_entry(
                    title=f"HK Aura Plus ({host})",
                    data=user_input,
                )
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _test_connection(self, host: str, port: int) -> bool:
        """Test if we can connect to the device."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5,
            )
            writer.close()
            await writer.wait_closed()
        except (OSError, asyncio.TimeoutError):
            _LOGGER.debug("Cannot connect to %s:%s", host, port)
            return False
        return True
