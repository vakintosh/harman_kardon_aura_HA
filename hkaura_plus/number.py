import asyncio
import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.restore_state import RestoreEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    device = hass.data[DOMAIN]
    async_add_entities([
        HKAuraBassControl(device),
        HKAuraVolumeControl(device)
    ], True)

class DebounceMixin:
    def __init__(self):
        self._debounce_task = None
        self._pending_value = None

    async def debounce_send(self, delay_seconds, send_func):
        """Debounce sending commands, cancelling previous tasks if still pending."""
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounce_worker(delay_seconds, send_func))

    async def _debounce_worker(self, delay_seconds, send_func):
        try:
            await asyncio.sleep(delay_seconds)
            await send_func(self._pending_value)
        except asyncio.CancelledError:
            pass

class HKAuraBassControl(DebounceMixin, NumberEntity, RestoreEntity):
    def __init__(self, device):
        super().__init__()
        self._device = device
        self._bass = 20

    @property
    def name(self):
        return "HK Aura Bass"

    @property
    def unique_id(self):
        return "hk_aura_bass"

    @property
    def native_value(self):
        return self._bass

    @property
    def native_min_value(self):
        return 0

    @property
    def native_max_value(self):
        return 100

    @property
    def native_step(self):
        return 1

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state.isdigit():
            self._bass = int(last_state.state)

    async def async_set_native_value(self, value: float) -> None:
        self._pending_value = int(value)

        async def send_bass(value):
            _LOGGER.debug(f"Setting bass to: {value}")
            await self._device.send_request("set_bass_level", para=value)
            self._bass = value
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_bass)

class HKAuraVolumeControl(DebounceMixin, NumberEntity, RestoreEntity):
    def __init__(self, device):
        super().__init__()
        self._device = device
        self._volume = 20

    @property
    def name(self):
        return "HK Aura Volume"

    @property
    def unique_id(self):
        return "hk_aura_volume"

    @property
    def native_value(self):
        return self._volume

    @property
    def native_min_value(self):
        return 0

    @property
    def native_max_value(self):
        return 100

    @property
    def native_step(self):
        return 1

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state.isdigit():
            self._volume = int(last_state.state)

    async def async_set_native_value(self, value: float) -> None:
        self._pending_value = int(value)

        async def send_volume(value):
            _LOGGER.debug(f"Setting volume to: {value}")
            await self._device.send_request("set_system_volume", para=value)
            self._volume = value
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_volume)
