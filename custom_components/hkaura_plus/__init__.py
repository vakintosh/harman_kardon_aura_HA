"""HK Aura Plus Speaker integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import CONF_MEDIA_PLAYER_ENTITY, DOMAIN, PLATFORMS
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)

type HKAuraConfigEntry = ConfigEntry[HKAuraData]


@dataclass(slots=True)
class HKAuraData:
    """Runtime data for HK Aura Plus."""

    device: HKDevice
    media_player_entity: str | None


async def async_setup_entry(hass: HomeAssistant, entry: HKAuraConfigEntry) -> bool:
    """Set up HK Aura Plus from a config entry."""
    device = HKDevice(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )

    entry.runtime_data = HKAuraData(
        device=device,
        media_player_entity=entry.data.get(CONF_MEDIA_PLAYER_ENTITY),
    )

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