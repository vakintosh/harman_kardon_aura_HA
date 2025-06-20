# __init__.py
from homeassistant.helpers.discovery import load_platform
from .speaker import HKDevice

DOMAIN = "hkaura_plus"

def setup(hass, config):
    """
    Set up the HK Aura Plus component.
    This function initializes the HK Aura Plus device and loads the necessary platforms.
    """
    ip = config[DOMAIN].get("ip_address")
    port = config[DOMAIN].get("port")

    device = HKDevice(ip, port)
    hass.data[DOMAIN] = device

    for platform in ("number", "switch"):
        load_platform(hass, platform, DOMAIN, {}, config)

    return True