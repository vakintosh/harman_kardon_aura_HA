"""Config flow for HK Aura Plus integration."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CONF_BT_MAC,
    CONF_MEDIA_PLAYER_ENTITY,
    CONF_WAKE_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_WAKE_TIMEOUT,
    DOMAIN,
)
from .hk_bt_device import BluetoothSpeaker
from .hk_bt_protocol import ProtocolError
from .rfcomm import RfcommUnavailable, RfcommError, rfcomm_supported

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MEDIA_PLAYER_ENTITY): str,
    }
)


MAC_RE = re.compile(r"^([0-9A-F]{2}[:-]){5}[0-9A-F]{2}$", re.IGNORECASE)

WAKE_TIMEOUT_VALIDATOR = vol.All(int, vol.Range(min=10, max=600))


def normalize_mac(value: str) -> str | None:
    """Return an upper-case colon-separated MAC, or None if malformed."""
    value = value.strip()
    if not MAC_RE.match(value):
        return None
    return value.replace("-", ":").upper()


async def validate_bluetooth(mac: str) -> str | None:
    """Probe the speaker over RFCOMM; return an error key or None if usable."""
    if not rfcomm_supported():
        return "bluetooth_unsupported"
    try:
        await BluetoothSpeaker(mac).power_state()
    except RfcommUnavailable:
        return "bluetooth_unsupported"
    except (RfcommError, ProtocolError):
        return "bluetooth_unreachable"
    return None


class HKAuraPlusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HK Aura Plus."""

    VERSION = 1

    _data: dict[str, Any]

    async def async_step_bluetooth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Optional Bluetooth step. Leave the MAC empty to stay Wi-Fi only."""
        errors: dict[str, str] = {}
        if user_input is not None:
            raw = (user_input.get(CONF_BT_MAC) or "").strip()
            if not raw:
                return self._create_entry(self._data)
            mac = normalize_mac(raw)
            if mac is None:
                errors[CONF_BT_MAC] = "invalid_mac"
            elif error := await validate_bluetooth(mac):
                errors[CONF_BT_MAC] = error
            else:
                return self._create_entry(
                    {
                        **self._data,
                        CONF_BT_MAC: mac,
                        CONF_WAKE_TIMEOUT: user_input.get(
                            CONF_WAKE_TIMEOUT, DEFAULT_WAKE_TIMEOUT
                        ),
                    }
                )

        return self.async_show_form(
            step_id="bluetooth",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_BT_MAC): str,
                    vol.Optional(
                        CONF_WAKE_TIMEOUT, default=DEFAULT_WAKE_TIMEOUT
                    ): WAKE_TIMEOUT_VALIDATOR,
                }
            ),
            errors=errors,
        )

    def _create_entry(self, data: dict[str, Any]) -> ConfigFlowResult:
        return self.async_create_entry(
            title=f"HK Aura Plus ({data[CONF_HOST]})", data=data
        )

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
                self._data = dict(user_input)
                return await self.async_step_bluetooth()
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration — allows updating media_player_entity after MA updates."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            data = dict(user_input)
            raw_mac = (data.pop(CONF_BT_MAC, "") or "").strip()
            if raw_mac:
                mac = normalize_mac(raw_mac)
                if mac is None:
                    errors[CONF_BT_MAC] = "invalid_mac"
                elif error := await validate_bluetooth(mac):
                    errors[CONF_BT_MAC] = error
                else:
                    data[CONF_BT_MAC] = mac
            else:
                data.pop(CONF_WAKE_TIMEOUT, None)  # Bluetooth removed

            if not errors:
                if await self._test_connection(host, port):
                    return self.async_update_reload_and_abort(
                        entry,
                        data=data,
                        reason="reconfigure_successful",
                    )
                errors["base"] = "cannot_connect"

        # Pre-fill form with existing values
        current = entry.data
        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)): int,
                vol.Optional(
                    CONF_MEDIA_PLAYER_ENTITY,
                    default=current.get(CONF_MEDIA_PLAYER_ENTITY, ""),
                ): str,
                vol.Optional(
                    CONF_BT_MAC, default=current.get(CONF_BT_MAC, "")
                ): str,
                vol.Optional(
                    CONF_WAKE_TIMEOUT,
                    default=current.get(CONF_WAKE_TIMEOUT, DEFAULT_WAKE_TIMEOUT),
                ): WAKE_TIMEOUT_VALIDATOR,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
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
        except (OSError, TimeoutError):
            _LOGGER.debug("Cannot connect to %s:%s", host, port)
            return False
        return True
