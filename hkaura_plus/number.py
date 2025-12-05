import asyncio
import logging
from homeassistant.components.number import NumberEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNKNOWN, STATE_UNAVAILABLE
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the HK Aura number controls."""
    data = hass.data[DOMAIN]
    device = data["device"]
    media_player_entity = data.get("media_player_entity")
    
    async_add_entities([
        HKAuraBassControl(device),
        HKAuraVolumeControl(device, media_player_entity)
    ], True)

class DebounceMixin:
    """
    Mixin to handle debouncing of commands.
    This mixin allows commands to be sent with a delay, cancelling any previous pending commands.
    It is useful for preventing rapid state changes from overwhelming the device.
    """
    def __init__(self):
        """
        Initialize the debounce mixin.
        This sets up the initial state for debouncing, including a task and a pending value.
        """
        self._debounce_task = None
        self._pending_value = None

    async def debounce_send(self, delay_seconds, send_func):
        """
        Debounce sending commands, cancelling previous tasks if still pending.
        This method will wait for a specified delay before executing the send function.
        If a new command is received before the delay expires, the previous command is cancelled.
        """
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()

        self._debounce_task = asyncio.create_task(self._debounce_worker(delay_seconds, send_func))

    async def _debounce_worker(self, delay_seconds, send_func):
        """
        Worker to handle the debouncing logic.
        This method waits for the specified delay and then calls the send function with the pending value.
        If the task is cancelled before the delay expires, it will not execute the send function.
        """
        try:
            await asyncio.sleep(delay_seconds)
            await send_func(self._pending_value)
        except asyncio.CancelledError:
            pass

class HKAuraBassControl(DebounceMixin, NumberEntity, RestoreEntity):
    """
    Number control for the bass level of the HK Aura speaker.
    This class allows users to adjust the bass level of the speaker through Home Assistant.
    """
    def __init__(self, device):
        """
        Initialize the bass control.
        This sets up the initial bass level and the device to communicate with.
        """
        super().__init__()
        self._device = device
        self._bass = 20

    @property
    def name(self):
        """
        Return the name of the bass control.
        """
        return "HK Aura Bass"

    @property
    def unique_id(self):
        """
        Return a unique ID for the bass control.
        """
        return "hk_aura_bass"

    @property
    def native_value(self):
        """
        Return the current bass level.
        """
        return self._bass

    @property
    def native_min_value(self):
        """
        Return the minimum bass level.
        """
        return 0

    @property
    def native_max_value(self):
        """
        Return the maximum bass level.
        """
        return 100

    @property
    def native_step(self):
        """
        Return the step size for bass level adjustments.
        """
        return 1

    async def async_added_to_hass(self):
        """
        Restore the last state of the bass control.
        This method retrieves the last known state of the bass level from Home Assistant's state store.
        If a valid state is found, it sets the current bass level to that value.
        If no valid state is found, it defaults to the initial bass level of 20.
        """
        last_state = await self.async_get_last_state()
        if last_state and last_state.state.isdigit():
            self._bass = int(last_state.state)

    async def async_set_native_value(self, value: float) -> None:
        """
        Set the bass level to a new value.
        This method is called when the user adjusts the bass level in Home Assistant.
        """
        self._pending_value = int(value)

        async def send_bass(value):
            """
            Send the bass level to the HK Aura speaker.
            This function sends the new bass level to the speaker using the device's send_request method.
            It logs the action and updates the internal state of the bass level.
            """
            _LOGGER.debug(f"Setting bass to: {value}")
            await self._device.send_request("set_bass_level", para=value)
            self._bass = value
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_bass)

class HKAuraVolumeControl(DebounceMixin, NumberEntity, RestoreEntity):
    """Number control for the volume of the HK Aura speaker."""
    def __init__(self, device, media_player_entity=None):
        """Initialize the volume control."""
        super().__init__()
        self._device = device
        self._volume = 20
        self._unsubscribe = None
        self._media_player_entity = media_player_entity

    @property
    def name(self):
        """Return the name of the volume control."""
        return "HK Aura Volume"

    @property
    def unique_id(self):
        """Return a unique ID for the volume control."""
        return "hk_aura_volume"

    @property
    def native_value(self):
        """Return the current volume level."""
        return self._volume

    @property
    def native_min_value(self):
        """Return the minimum volume level."""
        return 0

    @property
    def native_max_value(self):
        """Return the maximum volume level."""
        return 100

    @property
    def native_step(self):
        """Return the step size for volume adjustments."""
        return 1
    
    async def async_added_to_hass(self):
        """Restore the last state of the volume control and subscribe to media_player changes."""
        last_state = await self.async_get_last_state()
        if last_state and last_state.state.isdigit():
            self._volume = int(last_state.state)
        
        # Subscribe to media_player state changes
        if self._media_player_entity:
            self._unsubscribe = async_track_state_change_event(
                self.hass,
                [self._media_player_entity],
                self._handle_media_player_change
            )
            _LOGGER.info(f"Listening to volume changes from {self._media_player_entity}")

    async def async_will_remove_from_hass(self):
        """Unsubscribe from state changes when removed."""
        if self._unsubscribe:
            self._unsubscribe()

    async def _handle_media_player_change(self, event):
        """Handle media_player state changes and update volume."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return

        # Get volume_level attribute (0.0 to 1.0) and convert to 0-100
        volume_level = new_state.attributes.get("volume_level")
        if volume_level is not None:
            new_volume = int(volume_level * 100)
            if new_volume != self._volume:
                _LOGGER.debug(f"Volume changed externally to: {new_volume}")
                self._volume = new_volume
                self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set the volume to a new value."""
        self._pending_value = int(value)

        async def send_volume(value):
            """Send the volume level to the HK Aura speaker."""
            _LOGGER.debug(f"Setting volume to: {value}")
            await self._device.send_request("set_system_volume", para=value)
            self._volume = value
            self.async_write_ha_state()

        await self.debounce_send(0.5, send_volume)
