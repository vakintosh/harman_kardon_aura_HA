"""High-level Bluetooth API for the HK Aura Plus.

``wake`` is the only state-changing call. The power command is a toggle, so it
is guarded: the state is read first and the toggle is sent at most once, and
only when the speaker was read as being in standby.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

from . import hk_bt_protocol as proto
from .rfcomm import RFCOMM_CHANNEL, RfcommLink, open_link

_LOGGER = logging.getLogger(__name__)

CONFIRM_INTERVAL: Final = 1.0
# Seconds to wait for the Wi-Fi control port after a wake. Measured on
# hardware: 25-32 s typically, 58.4 s in the worst run, so 120 s.
DEFAULT_PORT_WAIT: Final = 120

Opener = Callable[..., Awaitable[RfcommLink]]
Sleeper = Callable[[float], Awaitable[None]]
PortReady = Callable[[], Awaitable[bool]]


@dataclass(frozen=True, slots=True)
class BtStatus:
    """Snapshot read over one connection; ``source`` is None in standby."""

    power: bool
    source: proto.Source | None


class WakeResult(Enum):
    """Outcome of a wake request."""

    ALREADY_ON = "already_on"
    WOKE = "woke"


class WakeFailed(Exception):
    """The toggle was sent but the speaker did not confirm power-on in time."""


class BluetoothSpeaker:
    """Control one speaker over RFCOMM using short-lived connections."""

    def __init__(
        self,
        mac: str,
        *,
        channel: int = RFCOMM_CHANNEL,
        opener: Opener = open_link,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self.mac = mac
        self._channel = channel
        self._open = opener
        self._sleep = sleep
        self._lock = asyncio.Lock()

    async def _link(self) -> RfcommLink:
        return await self._open(self.mac, self._channel)

    async def power_state(self) -> bool:
        """Return True if on, False in standby."""
        async with self._lock:
            link = await self._link()
            try:
                return await self._read_power(link)
            finally:
                link.close()

    async def status(self) -> BtStatus:
        """Read power, and the source if the speaker is on, in one connection."""
        async with self._lock:
            link = await self._link()
            try:
                if not await self._read_power(link):
                    return BtStatus(power=False, source=None)
                reply = await link.request(proto.QUERY_SOURCE, proto.TYPE_SOURCE)
                return BtStatus(power=True, source=proto.decode_source(reply))
            finally:
                link.close()

    async def source(self) -> proto.Source:
        """Return the current input source."""
        async with self._lock:
            link = await self._link()
            try:
                reply = await link.request(proto.QUERY_SOURCE, proto.TYPE_SOURCE)
                return proto.decode_source(reply)
            finally:
                link.close()

    async def wake(
        self,
        *,
        confirm_attempts: int = 10,
        port_ready: PortReady | None = None,
        port_wait: float = DEFAULT_PORT_WAIT,
    ) -> WakeResult:
        """Wake the speaker from standby, safely.

        Never sends the toggle unless power was read as off in this same
        connection; never sends it twice.
        """
        result = WakeResult.ALREADY_ON
        async with self._lock:
            link = await self._link()
            try:
                if not await self._read_power(link):
                    _LOGGER.debug("Speaker in standby, sending power toggle")
                    await link.send(proto.POWER_TOGGLE)
                    await self._confirm_on(link, confirm_attempts)
                    result = WakeResult.WOKE
            finally:
                link.close()
        # Also when already on: after a power cut the speaker can report "on"
        # while its Wi-Fi is still booting, so callers still need the port.
        if port_ready is not None:
            await self._wait_port(port_ready, port_wait)
        return result

    @staticmethod
    async def _read_power(link: Any) -> bool:
        reply = await link.request(proto.QUERY_POWER, proto.TYPE_POWER)
        return proto.decode_power(reply)

    async def _confirm_on(self, link: Any, attempts: int) -> None:
        for _ in range(attempts):
            await self._sleep(CONFIRM_INTERVAL)
            if await self._read_power(link):
                return
        raise WakeFailed(f"speaker did not report power on after {attempts} checks")

    async def _wait_port(self, port_ready: PortReady, port_wait: float) -> None:
        for _ in range(max(1, int(port_wait / CONFIRM_INTERVAL))):
            if await port_ready():
                return
            await self._sleep(CONFIRM_INTERVAL)
        raise WakeFailed("control port did not open after wake")
