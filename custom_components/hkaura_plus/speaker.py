"""Device communication for HK Aura Plus speaker."""
from __future__ import annotations

import asyncio
import logging
from string import Template

from .const import ACTIONS, DEFAULT_PORT, TIMEOUT

_LOGGER = logging.getLogger(__name__)

XML_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<harman>
  <mm>
    <common>
      <control>
        <name>${action}</name>
        <zone>${zone}</zone>
        <para>${para}</para>
      </control>
    </common>
  </mm>
</harman>"""


class HKDevice:
    """Interact with the HK Aura speaker over TCP."""

    __slots__ = ("host", "port", "_available")

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        """Initialize the HKDevice."""
        self.host = host
        self.port = port
        self._available = True

    @property
    def available(self) -> bool:
        """Return whether the device is reachable."""
        return self._available

    async def send_request(
        self, action: str, zone: str = "Main Zone", para: str | int | None = None
    ) -> None:
        """Send a request to the HK Aura speaker."""
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        if action == "set_EQ_mode":
            if para == "off":
                para = "Basic"
            elif para == "on":
                para = "Stereo Widening"
            else:
                raise ValueError("EQ mode must be 'on' or 'off'.")

        xml_data = Template(XML_TEMPLATE).substitute(
            action=action, zone=zone, para=para if para is not None else ""
        )

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=TIMEOUT,
            )

            writer.write(xml_data.encode("utf-8"))
            await writer.drain()

            try:
                response = await asyncio.wait_for(reader.read(1024), timeout=1)
                _LOGGER.debug(
                    "Response: %s", response.decode("utf-8", errors="ignore")
                )
            except TimeoutError:
                pass

            writer.close()
            await writer.wait_closed()

            self._available = True
            _LOGGER.debug("Sent action=%s, para=%s", action, para)

        except (OSError, TimeoutError) as err:
            self._available = False
            _LOGGER.error("Cannot reach %s:%s: %s", self.host, self.port, err)
            raise