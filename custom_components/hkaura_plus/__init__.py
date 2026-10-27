"""HK Aura Plus Speaker integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import Event, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_BT_MAC,
    CONF_MEDIA_PLAYER_ENTITY,
    CONF_WAKE_TIMEOUT,
    DEFAULT_WAKE_TIMEOUT,
    DOMAIN,
    PLATFORMS,
    SERVICE_WAKE,
)
from .coordinator import HKAuraBtCoordinator
from .hk_bt_device import BluetoothSpeaker
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)

type HKAuraConfigEntry = ConfigEntry[HKAuraData]


@dataclass(slots=True)
class HKAuraData:
    """Runtime data for HK Aura Plus."""

    device: HKDevice
    media_player_entity: str | None
    bluetooth: BluetoothSpeaker | None = None
    coordinator: HKAuraBtCoordinator | None = None


WAKE_SCHEMA = vol.Schema(
    {
        vol.Optional("config_entry_id"): str,
        vol.Optional("timeout"): vol.All(vol.Coerce(float), vol.Range(min=1, max=600)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration-wide wake service."""

    async def _handle_wake(call: ServiceCall) -> None:
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
            and e.runtime_data.coordinator is not None
        ]
        wanted = call.data.get("config_entry_id")
        if wanted:
            entries = [e for e in entries if e.entry_id == wanted]
        if not entries:
            raise ServiceValidationError(
                "No speaker with Bluetooth configured (add a Bluetooth MAC in the "
                "integration options)."
            )
        if len(entries) > 1:
            raise ServiceValidationError(
                "Several speakers have Bluetooth; pass config_entry_id."
            )
        await entries[0].runtime_data.coordinator.async_wake(call.data.get("timeout"))

    hass.services.async_register(DOMAIN, SERVICE_WAKE, _handle_wake, schema=WAKE_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HKAuraConfigEntry) -> bool:
    """Set up HK Aura Plus from a config entry."""
    device = HKDevice(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )

    data = HKAuraData(
        device=device,
        media_player_entity=entry.data.get(CONF_MEDIA_PLAYER_ENTITY),
    )
    if mac := entry.data.get(CONF_BT_MAC):
        data.bluetooth = BluetoothSpeaker(mac)
        data.coordinator = HKAuraBtCoordinator(
            hass,
            entry,
            data.bluetooth,
            device,
            entry.data.get(CONF_WAKE_TIMEOUT, DEFAULT_WAKE_TIMEOUT),
        )
        # Never block or fail setup because of Bluetooth: Wi-Fi entities must
        # keep working. Failures show up as unavailable Bluetooth entities.
        await data.coordinator.async_refresh()
        # Starting playback is what flips the speaker's input to AirPlay, so
        # refresh right away when the linked media player changes state.
        if data.media_player_entity:
            coordinator = data.coordinator

            async def _refresh(_event: Event) -> None:
                await coordinator.async_request_refresh()

            entry.async_on_unload(
                async_track_state_change_event(
                    hass, [data.media_player_entity], _refresh
                )
            )
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug(
        "HK Aura Plus setup completed for %s:%s",
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HKAuraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)