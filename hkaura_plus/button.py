"""Button entities for Harman Kardon Aura Plus."""
import logging

from homeassistant.components.button import ButtonEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the HK Aura button entities."""
    data = hass.data[DOMAIN]
    device = data["device"]
    
    add_entities([
        HKAuraPowerOffButton(device),
    ])


class HKAuraPowerOffButton(ButtonEntity):
    """Power Off button for HK Aura Plus speaker."""

    def __init__(self, device):
        """Initialize the button."""
        self._device = device
        self._attr_name = "HK Aura Power Off"
        self._attr_unique_id = f"{device.host}_power_off"
        self._attr_icon = "mdi:power"

    def press(self) -> None:
        """Handle the button press."""
        _LOGGER.info("Powering off HK Aura Plus speaker")
        self._device.send_command("power-off")

