# __init__.py
import logging
import voluptuous as vol
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hkaura_plus"
CONF_MEDIA_PLAYER_ENTITY = "media_player_entity"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("ip_address"): cv.string,
        vol.Required("port"): cv.port,
        vol.Optional("device_name"): cv.string,
        vol.Optional(CONF_MEDIA_PLAYER_ENTITY): cv.entity_id,
    })
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    """
    Set up the HK Aura Plus component.
    This function initializes the HK Aura Plus device and loads the necessary platforms.
    """
    ip = config[DOMAIN].get("ip_address")
    port = config[DOMAIN].get("port")
    media_player_entity = config[DOMAIN].get(CONF_MEDIA_PLAYER_ENTITY)

    device = HKDevice(ip, port)
    
    # Store both device and configuration
    hass.data[DOMAIN] = {
        "device": device,
        "media_player_entity": media_player_entity
    }
    
    _LOGGER.info(f"HK Aura Plus setup completed for {ip}:{port}")
    if media_player_entity:
        _LOGGER.info(f"Will sync volume with media_player: {media_player_entity}")

    for platform in ("number", "switch"):
        load_platform(hass, platform, DOMAIN, {}, config)

    return True