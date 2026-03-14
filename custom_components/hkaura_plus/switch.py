"""Switch entities for HK Aura Plus speaker."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import HKAuraConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HKAuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HK Aura switches."""
    device = entry.runtime_data.device
    async_add_entities(
        [
            HKAuraEQSwitch(device, entry.entry_id),
            HKAuraMuteSwitch(device, entry.entry_id),
        ],
        True,
    )


class HKAuraEQSwitch(SwitchEntity, RestoreEntity):
    """Switch to control the EQ mode of the HK Aura speaker."""

    _attr_has_entity_name = True
    _attr_translation_key = "eq_mode"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, device: HKDevice, entry_id: str) -> None:
        """Initialize the EQ switch."""
        self._device = device
        self._attr_is_on = False
        self._attr_unique_id = f"{entry_id}_eq_mode"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the EQ mode."""
        try:
            await self._device.send_request("set_EQ_mode", para="on")
        except (OSError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Failed to turn on EQ mode: {err}"
            ) from err
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the EQ mode."""
        try:
            await self._device.send_request("set_EQ_mode", para="off")
        except (OSError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Failed to turn off EQ mode: {err}"
            ) from err
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last state of the switch."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._attr_is_on = True


class HKAuraMuteSwitch(SwitchEntity, RestoreEntity):
    """Switch to control the mute state of the HK Aura speaker."""

    _attr_has_entity_name = True
    _attr_translation_key = "mute"
    _attr_should_poll = False

    def __init__(self, device: HKDevice, entry_id: str) -> None:
        """Initialize the mute switch."""
        self._device = device
        self._attr_is_on = False
        self._attr_unique_id = f"{entry_id}_mute"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Mute the speaker."""
        try:
            await self._device.send_request("mute-on")
        except (OSError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Failed to mute speaker: {err}"
            ) from err
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unmute the speaker."""
        try:
            await self._device.send_request("mute-off")
        except (OSError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Failed to unmute speaker: {err}"
            ) from err
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore the last state of the switch."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._attr_is_on = True