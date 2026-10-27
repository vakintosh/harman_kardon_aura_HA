"""Read-only input-source sensor for HK Aura Plus (Bluetooth control channel).

Reading works and was verified on hardware. Writing the source over RFCOMM does
not: the speaker steps through inputs instead of selecting the requested one,
so there is deliberately no setter.
"""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HKAuraConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HKAuraBtCoordinator
from .hk_bt_protocol import Source


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HKAuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bluetooth sensors (only when Bluetooth is configured)."""
    if (coordinator := entry.runtime_data.coordinator) is not None:
        async_add_entities([HKAuraSourceSensor(coordinator, entry.entry_id)])


class HKAuraSourceSensor(CoordinatorEntity[HKAuraBtCoordinator], SensorEntity):
    """The speaker's current input; unknown in standby."""

    _attr_has_entity_name = True
    _attr_translation_key = "source"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [source.name.lower() for source in Source]

    def __init__(self, coordinator: HKAuraBtCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_source"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="HK Aura Plus",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def native_value(self) -> str | None:
        """Current source name, or None when unknown (standby)."""
        source = self.coordinator.data.source
        return None if source is None else source.name.lower()
