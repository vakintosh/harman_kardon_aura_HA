# number.py
from homeassistant.components.number import NumberEntity
from . import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    device = hass.data[DOMAIN]
    async_add_entities([
        HKAuraBassControl(device),
        HKAuraVolumeControl(device)
    ], True)

class HKAuraBassControl(NumberEntity):
    def __init__(self, device):
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

    async def async_set_native_value(self, value: float) -> None:
        bass = int(value)
        _LOGGER.debug(f"Setting bass to: {bass}")
        await self._device.send_request("set_bass_level", para=bass)
        self._bass = bass
        self.async_write_ha_state()

class HKAuraVolumeControl(NumberEntity):
    def __init__(self, device):
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

    async def async_set_native_value(self, value: float) -> None:
        volume = int(value)
        _LOGGER.debug(f"Setting volume to: {volume}")
        await self._device.send_request("set_system_volume", para=volume)
        self._volume = volume
        self.async_write_ha_state()
