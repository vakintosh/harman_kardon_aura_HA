# switch.py
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    device = hass.data[DOMAIN]
    async_add_entities([
        HKAuraEQSwitch(device),
        HKAuraMuteSwitch(device)
    ], True)


class HKAuraEQSwitch(SwitchEntity, RestoreEntity):
    def __init__(self, device):
        self._device = device
        self._is_on = False

    @property
    def name(self):
        return "HK Aura EQ Mode"

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self, **kwargs):
        self._device.send_command("set_EQ_mode", para="on")
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self._device.send_command("set_EQ_mode", para="off")
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._is_on = True

    async def async_update(self):
        pass


class HKAuraMuteSwitch(SwitchEntity, RestoreEntity):
    def __init__(self, device):
        self._device = device
        self._is_on = False

    @property
    def name(self):
        return "HK Aura Mute"

    @property
    def is_on(self):
        return self._is_on

    def turn_on(self, **kwargs):
        self._device.send_command("mute-on")
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        self._device.send_command("mute-off")
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._is_on = True

    async def async_update(self):
        pass