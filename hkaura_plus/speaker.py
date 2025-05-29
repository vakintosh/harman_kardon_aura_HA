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
    def __init__(self, host, port=DEFAULT_PORT):
        self.host = host
        self.port = port

    async def send_request(self, action, zone="Main Zone", para=None):
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
        asyncio.run(self.send_request(action, para=para))
