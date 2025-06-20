# speaker.py
import asyncio
import aiohttp
import async_timeout
import logging
from string import Template
import os

_LOGGER = logging.getLogger(__name__)

ACTIONS = {
    'set_system_volume': {'name': 'set_system_volume', 'para_range': (0, 100)},
    'set_bass_level': {'name': 'set_bass_level', 'para_range': (0, 100)},
    'set_EQ_mode': {'name': 'set_EQ_mode', 'para_options': ['on', 'off']},
    'heart-alive': {'name': 'heart-alive'},
    'power-off': {'name': 'power-off'},
    'mute-off': {'name': 'mute-off'},
    'mute-on': {'name': 'mute-on'},
}

DEFAULT_PORT = 10025
TIMEOUT = 2

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'hk_request_template.xml')
with open(TEMPLATE_PATH, encoding='utf-8') as f:
    XML_TEMPLATE = f.read()

class HKDevice:
    """
    Class to interact with the HK Aura speaker.
    This class provides methods to send commands to the speaker using HTTP requests.
    It supports actions like setting volume, bass level, EQ mode, and more.
    The device communicates over HTTP, and the commands are sent as XML formatted strings.
    The class uses aiohttp for asynchronous HTTP requests and async_timeout for request timeouts.
    It also includes error handling for unknown actions and connection issues.
    The XML template for requests is loaded from a file, allowing for easy modification of the request format.
    """
    def __init__(self, host, port=DEFAULT_PORT):
        """
        Initialize the HKDevice with host and port.
        """
        self.host = host
        self.port = port

    async def send_request(self, action, zone="Main Zone", para=None):
        """
        Send a request to the HK Aura speaker.
        This method constructs an XML request based on the action and parameters provided.
        It uses aiohttp to send the request and handles the response.
        """
        url = f"http://{self.host}:{self.port}"
        headers = {'Content-Type': 'application/xml', 'Connection': 'close'}

        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        if action == 'set_EQ_mode':
            if para == 'off':
                para = 'Basic'
            elif para == 'on':
                para = 'Stereo Widening'
            else:
                raise ValueError("EQ mode must be 'on' or 'off'.")

        xml_data = Template(XML_TEMPLATE).substitute(action=action, zone=zone, para=para or "")
        connector = aiohttp.TCPConnector(ssl=False)

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with async_timeout.timeout(TIMEOUT):
                    async with session.post(url, data=xml_data, headers=headers) as response:
                        if response.status == 200:
                            _LOGGER.debug(f"Sent action={action}, para={para}")
                        else:
                            _LOGGER.warning(f"Failed to send: {response.status} -> {await response.text()}")
        except Exception as e:
            _LOGGER.error(f"Exception while sending request: {e}")


    def send_command(self, action, para=None):
        """
        Send a command to the HK Aura speaker.
        This method is a synchronous wrapper around the asynchronous send_request method.
        It allows for easier integration with synchronous code.
        """
        asyncio.run(self.send_request(action, para=para))
