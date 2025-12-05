# speaker.py
import asyncio
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
    This class provides methods to send commands to the speaker using TCP sockets.
    It supports actions like setting volume, bass level, EQ mode, and more.
    The device communicates over raw TCP, and the commands are sent as XML formatted strings.
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
        It uses asyncio TCP connection to send the request.
        """
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

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=TIMEOUT
            )
            
            writer.write(xml_data.encode('utf-8'))
            await writer.drain()
            
            try:
                response = await asyncio.wait_for(reader.read(1024), timeout=1)
                _LOGGER.debug(f"Response: {response.decode('utf-8', errors='ignore')}")
            except asyncio.TimeoutError:
                pass  
            
            writer.close()
            await writer.wait_closed()
            
            _LOGGER.debug(f"Sent action={action}, para={para}")
            
        except Exception as e:
            _LOGGER.error(f"Exception while sending request: {e}")

    def send_command(self, action, para=None):
        """
        Send a command to the HK Aura speaker.
        This method is a synchronous wrapper around the asynchronous send_request method.
        """
        asyncio.run(self.send_request(action, zone="Main Zone", para=para))