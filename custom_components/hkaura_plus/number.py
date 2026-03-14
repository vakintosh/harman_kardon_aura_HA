"""Number entities for HK Aura Plus speaker."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
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
    """Set up the HK Aura number controls."""
    data = entry.runtime_data
    device = data.device
    media_player_entity = data.media_player_entity

    async_add_entities(
        [
            HKAuraBassControl(device, entry.entry_id),
            HKAuraVolumeControl(device, entry.entry_id, media_player_entity),
        ],
        True,
    )


class DebounceMixin:
    """Mixin to debounce commands sent to the device."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the debounce mixin."""
        super().__init__(*args, **kwargs)
        self._debounce_task: asyncio.Task[None] | None = None
        self._pending_value: int | None = None

    async def debounce_send(
        self,
        delay_seconds: float,
        send_func: Callable[[int], Coroutine[Any, Any, None]],
    ) -> None:
        """Debounce sending commands, cancelling previous tasks if still pending."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(
            self._debounce_worker(delay_seconds, send_func)
        )

    async def _debounce_worker(
        self,
        delay_seconds: float,
        send_func: Callable[[int], Coroutine[Any, Any, None]],
    ) -> None:
        """Wait then send the pending value."""
        try:
            await asyncio.sleep(delay_seconds)
            if self._pending_value is not None:
                await send_func(self._pending_value)
        except asyncio.CancelledError:
            pass


class HKAuraBassControl(DebounceMixin, NumberEntity, RestoreEntity):
    """Number control for the bass level of the HK Aura speaker."""

    _attr_has_entity_name = True
    _attr_translation_key = "bass"
    _attr_name = "Bass"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_should_poll = False

    def __init__(self, device: HKDevice, entry_id: str) -> None:
        """Initialize the bass control."""
        super().__init__()
        self._device = device
        self._bass = 20
        self._attr_unique_id = f"{entry_id}_bass"
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

    @property
    def native_value(self) -> int:
        """Return the current bass level."""
        return self._bass

    async def async_added_to_hass(self) -> None:
        """Restore the last state of the bass control."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._bass = int(float(last_state.state))
            except (ValueError, TypeError):
                pass

    async def async_set_native_value(self, value: float) -> None:
        """Set the bass level to a new value."""
        self._pending_value = int(value)

        async def send_bass(val: int) -> None:
            _LOGGER.debug("Setting bass to: %s", val)
            await self._device.send_request("set_bass_level", para=val)
            self._bass = val
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_bass)


class HKAuraVolumeControl(DebounceMixin, NumberEntity, RestoreEntity):
    """Number control for the volume of the HK Aura speaker."""

    _attr_has_entity_name = True
    _attr_translation_key = "volume"
    _attr_name = "Volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_should_poll = False

    def __init__(
        self,
        device: HKDevice,
        entry_id: str,
        media_player_entity: str | None = None,
    ) -> None:
        """Initialize the volume control."""
        super().__init__()
        self._device = device
        self._volume = 20
        self._unsubscribe: Callable[[], None] | None = None
        self._media_player_entity = media_player_entity
        self._attr_unique_id = f"{entry_id}_volume"
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

    @property
    def native_value(self) -> int:
        """Return the current volume level."""
        return self._volume

    async def async_added_to_hass(self) -> None:
        """Restore state and subscribe to media_player changes."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            try:
                self._volume = int(float(last_state.state))
            except (ValueError, TypeError):
                pass

        if self._media_player_entity:
            self._unsubscribe = async_track_state_change_event(
                self.hass,
                [self._media_player_entity],
                self._handle_media_player_change,
            )
            _LOGGER.debug(
                "Listening to volume changes from %s", self._media_player_entity
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from state changes when removed."""
        if self._unsubscribe:
            self._unsubscribe()

    async def _handle_media_player_change(self, event: Event) -> None:
        """Handle media_player state changes and update volume."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        volume_level = new_state.attributes.get("volume_level")
        if volume_level is not None:
            try:
                new_volume = int(float(volume_level) * 100)
                if new_volume != self._volume:
                    _LOGGER.debug("Volume changed externally to: %s", new_volume)
                    self._pending_value = new_volume

                    async def send_volume(val: int) -> None:
                        await self._device.send_request(
                            "set_system_volume", para=val
                        )
                        self._volume = val
                        self.async_write_ha_state()

                    await self.debounce_send(0.5, send_volume)
            except (ValueError, TypeError) as err:
                _LOGGER.error(
                    "Failed to process volume_level %s: %s", volume_level, err
                )
            except (OSError, TimeoutError) as err:
                _LOGGER.error(
                    "Failed to send volume to speaker: %s", err
                )

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume to a new value."""
        self._pending_value = int(value)

        async def send_volume(val: int) -> None:
            _LOGGER.debug("Setting volume to: %s", val)
            await self._device.send_request("set_system_volume", para=val)
            self._volume = val
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_volume)
