"""Constants for the HK Aura Plus integration."""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "hkaura_plus"

CONF_MEDIA_PLAYER_ENTITY: Final = "media_player_entity"

DEFAULT_PORT: Final = 10025
TIMEOUT: Final = 2

MANUFACTURER: Final = "Harman Kardon"
MODEL: Final = "Aura Plus"

ACTIONS: Final = {
    "heart-alive": {"name": "heart-alive"},
    "mute-off": {"name": "mute-off"},
    "mute-on": {"name": "mute-on"},
    "power-off": {"name": "power-off"},
    "set_EQ_mode": {"name": "set_EQ_mode", "para_options": ["on", "off"]},
    "set_bass_level": {"name": "set_bass_level", "para_range": (0, 100)},
    "set_system_volume": {"name": "set_system_volume", "para_range": (0, 100)},
}

PLATFORMS: Final = [Platform.BUTTON, Platform.NUMBER, Platform.SWITCH]
