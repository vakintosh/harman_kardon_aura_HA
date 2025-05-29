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

class HKAuraBassControl(NumberEntity, RestoreEntity):
    def __init__(self, device):
        self._device = device
        self._bass = 20
        self._debounce_task = None
        self._pending_bass = None

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
        self._pending_bass = int(value)
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounce_send())

    async def _debounce_send(self):
        try:
            await asyncio.sleep(0.5)
            bass = self._pending_bass
            _LOGGER.debug(f"Setting bass to: {bass}")
            await self._device.send_request("set_bass_level", para=bass)
            self._bass = bass
            self.async_write_ha_state()
        except asyncio.CancelledError:
            pass

class HKAuraVolumeControl(NumberEntity, RestoreEntity):
    def __init__(self, device):
        self._device = device
        self._volume = 20
        self._debounce_task = None
        self._pending_volume = None

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
        self._pending_volume = int(value)
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounce_send())

    async def _debounce_send(self):
        try:
            await asyncio.sleep(0.5)
            volume = self._pending_volume
            _LOGGER.debug(f"Setting volume to: {volume}")
            await self._device.send_request("set_system_volume", para=volume)
            self._volume = volume
            self.async_write_ha_state()
        except asyncio.CancelledError:
            pass
