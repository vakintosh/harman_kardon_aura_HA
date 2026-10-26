"""Source select for HK Aura Plus (Bluetooth control channel)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HKAuraConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import HKAuraBtCoordinator
from .hk_bt_protocol import Source
from .rfcomm import RfcommError

SELECTABLE = (Source.AIRPLAY, Source.BLUETOOTH, Source.AUX, Source.OPTICAL)
OPTION_TO_SOURCE = {s.name.lower(): s for s in SELECTABLE}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HKAuraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the source select (only when Bluetooth is configured)."""
    if (coordinator := entry.runtime_data.coordinator) is not None:
        async_add_entities([HKAuraSourceSelect(coordinator, entry.entry_id)])


class HKAuraSourceSelect(CoordinatorEntity[HKAuraBtCoordinator], SelectEntity):
    """Select the speaker's input source."""

    _attr_has_entity_name = True
    _attr_translation_key = "source"
    _attr_options = list(OPTION_TO_SOURCE)

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
    def current_option(self) -> str | None:
        """Current source; unknown (None) in standby or for unlisted sources."""
        source = self.coordinator.data.source
        if source is None or source not in SELECTABLE:
            return None
        return source.name.lower()

    async def async_select_option(self, option: str) -> None:
        """Change the source. The speaker must be on."""
        if not self.coordinator.data.power:
            raise HomeAssistantError("Speaker is in standby; wake it first.")
        try:
            await self.coordinator.bluetooth.set_source(OPTION_TO_SOURCE[option])
        except RfcommError as err:
            raise HomeAssistantError(f"Could not set source: {err}") from err
        await self.coordinator.async_request_refresh()
