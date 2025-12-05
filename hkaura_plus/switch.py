# switch.py
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """
    Set up the HK Aura switches.
    This function initializes the switches for EQ mode and mute control.
    It creates instances of HKAuraEQSwitch and HKAuraMuteSwitch and adds them to Home Assistant.
    """
    data = hass.data[DOMAIN]
    device = data["device"]
    async_add_entities([
        HKAuraEQSwitch(device),
        HKAuraMuteSwitch(device)
    ], True)


class HKAuraEQSwitch(SwitchEntity, RestoreEntity):
    """
    Switch to control the EQ mode of the HK Aura speaker.
    This switch allows the user to turn the EQ mode on or off.
    When turned on, it sends a command to set the EQ mode to 'on', and when turned off, it sets it to 'off'.
    The switch also restores its last state when added to Home Assistant.
    The EQ mode is a feature of the HK Aura speaker that adjusts the sound profile.
    """
    def __init__(self, device):
        self._device = device
        self._is_on = False

    @property
    def name(self):
        """
        Return the name of the switch.
        """
        return "HK Aura EQ Mode"

    @property
    def is_on(self):
        """
        Return True if the EQ mode is on.
        """
        return self._is_on

    def turn_on(self, **kwargs):
        """
        Turn on the EQ mode.
        This method sends a command to the HK Aura speaker to enable the EQ mode.
        """
        self._device.send_command("set_EQ_mode", para="on")
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """
        Turn off the EQ mode.
        This method sends a command to the HK Aura speaker to disable the EQ mode.
        """
        self._device.send_command("set_EQ_mode", para="off")
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """
        Restore the last state of the switch.
        This method is called when the switch is added to Home Assistant.
        It retrieves the last state from the restore state service and sets the switch's state accordingly.
        """
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._is_on = True

    async def async_update(self):
        """
        Update the switch state.
        This method is called periodically to update the switch's state.
        Currently, it does not perform any actions but can be extended in the future.
        """
        pass


class HKAuraMuteSwitch(SwitchEntity, RestoreEntity):
    """
    Switch to control the mute state of the HK Aura speaker.
    This switch allows the user to mute or unmute the speaker.
    When turned on, it sends a command to mute the speaker, and when turned off, it unmutes the speaker.
    The switch also restores its last state when added to Home Assistant.
    The mute switch is useful for quickly silencing the speaker without adjusting the volume.
    """
    def __init__(self, device):
        """
        Initialize the mute switch.
        This method sets up the device and initializes the mute state.
        """
        self._device = device
        self._is_on = False

    @property
    def name(self):
        """
        Return the name of the switch.
        """
        return "HK Aura Mute"

    @property
    def is_on(self):
        """
        Return True if the mute mode is on.
        This property checks the current mute state of the speaker.
        """
        return self._is_on

    def turn_on(self, **kwargs):
        """
        Turn on the mute mode.
        This method sends a command to the HK Aura speaker to mute the audio.
        It updates the internal state to reflect that the speaker is muted.
        """
        self._device.send_command("mute-on")
        self._is_on = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """
        Turn off the mute mode.
        This method sends a command to the HK Aura speaker to unmute the audio.
        It updates the internal state to reflect that the speaker is unmuted.
        """
        self._device.send_command("mute-off")
        self._is_on = False
        self.schedule_update_ha_state()

    async def async_added_to_hass(self):
        """
        Restore the last state of the switch.
        This method is called when the switch is added to Home Assistant.
        It retrieves the last state from the restore state service and sets the switch's state accordingly.
        """
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            self._is_on = True

    async def async_update(self):
        """
        Update the switch state.
        This method is called periodically to update the switch's state.
        Currently, it does not perform any actions but can be extended in the future.
        """
        pass