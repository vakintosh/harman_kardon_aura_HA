"""Bluetooth power-state sensor for HK Aura Plus (works while Wi-Fi is down)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HKAuraConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HKAuraBtCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HKAuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bluetooth binary sensors (only when Bluetooth is configured)."""
    if (coordinator := entry.runtime_data.coordinator) is not None:
        async_add_entities([HKAuraBtPowerSensor(coordinator, entry.entry_id)])


class HKAuraBtPowerSensor(CoordinatorEntity[HKAuraBtCoordinator], BinarySensorEntity):
    """On when the speaker is awake, off in standby (read over Bluetooth)."""

    _attr_has_entity_name = True
    _attr_translation_key = "bt_power"
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator: HKAuraBtCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_bt_power"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="HK Aura Plus",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def is_on(self) -> bool:
        """Return True when the speaker is on."""
        return self.coordinator.data.power
