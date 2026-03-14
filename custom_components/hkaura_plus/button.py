"""Button entities for HK Aura Plus speaker."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HKAuraConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HKAuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HK Aura button entities."""
    device = entry.runtime_data.device

    async_add_entities([HKAuraPowerOffButton(device, entry.entry_id)])


class HKAuraPowerOffButton(ButtonEntity):
    """Power Off button for HK Aura Plus speaker."""

    _attr_has_entity_name = True
    _attr_translation_key = "power_off"
    _attr_name = "Power off"

    def __init__(self, device: HKDevice, entry_id: str) -> None:
        """Initialize the button."""
        self._device = device
        self._attr_unique_id = f"{entry_id}_power_off"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="HK Aura Plus",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.available

    async def async_press(self) -> None:
        """Handle the button press."""
        _LOGGER.debug("Powering off HK Aura Plus speaker")
        try:
            await self._device.send_request("power-off")
        except (OSError, TimeoutError) as err:
            raise HomeAssistantError(
                f"Failed to power off speaker: {err}"
            ) from err

