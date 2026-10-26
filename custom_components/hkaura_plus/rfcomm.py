"""Async RFCOMM transport for the HK Aura Plus Bluetooth control channel.

Short-lived connections: open, exchange a few frames, close. The first query
after a cold connect is sometimes dropped by the speaker, so ``request``
resends on timeout.
"""
from __future__ import annotations

import asyncio
import errno
import socket
import time
from collections.abc import Awaitable, Callable
from typing import Final

from . import hk_bt_protocol as proto

RFCOMM_CHANNEL: Final = 2  # SDP: Serial Port 0x1101 (btmon_trace_1.md)
CONNECT_TIMEOUT: Final = 15.0
BUSY_RETRIES: Final = 5
BUSY_BACKOFF: Final = 0.5

_UNAVAILABLE_ERRNOS = {errno.ENODEV, errno.EAFNOSUPPORT, errno.EPERM, errno.EACCES,
                       errno.EPROTONOSUPPORT, errno.ENOPROTOOPT}

Connector = Callable[[str, int], Awaitable[socket.socket]]


class RfcommError(Exception):
    """Base class for transport errors."""


class RfcommUnavailable(RfcommError):
    """Bluetooth/RFCOMM cannot be used on this host (no adapter, no support, no permission)."""


class RfcommUnreachable(RfcommError):
    """The speaker did not accept the connection or stopped answering."""


def rfcomm_supported() -> bool:
    """Return True if this host can create an RFCOMM socket."""
    if not hasattr(socket, "AF_BLUETOOTH"):
        return False
    try:
        socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
        ).close()
    except OSError:
        return False
    return True


async def _default_connector(mac: str, channel: int) -> socket.socket:
    if not hasattr(socket, "AF_BLUETOOTH"):
        raise OSError(errno.EAFNOSUPPORT, "AF_BLUETOOTH not available")
    sock = socket.socket(
        socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM
    )
    sock.setblocking(False)
    try:
        await asyncio.wait_for(
            asyncio.get_running_loop().sock_connect(sock, (mac, channel)),
            CONNECT_TIMEOUT,
        )
    except BaseException:
        sock.close()
        raise
    return sock


class RfcommLink:
    """A connected RFCOMM socket speaking the Harman frame protocol."""

    def __init__(self, sock: socket.socket) -> None:
        sock.setblocking(False)
        self._sock = sock

    async def send(self, frame: bytes) -> None:
        """Send a frame without waiting for a reply."""
        try:
            await asyncio.get_running_loop().sock_sendall(self._sock, frame)
        except OSError as err:
            raise RfcommUnreachable(str(err)) from err

    async def request(
        self, frame: bytes, reply_type: int, *, timeout: float = 3.0, retries: int = 2
    ) -> bytes:
        """Send ``frame`` and return the reply of ``reply_type``.

        Unrelated frames (other types) are skipped. On timeout the frame is
        resent up to ``retries`` times.
        """
        for _ in range(retries + 1):
            await self.send(frame)
            try:
                return await self._read_until(reply_type, timeout)
            except TimeoutError:
                continue
        raise RfcommUnreachable(f"no type {reply_type:#04x} reply after {retries + 1} tries")

    async def _read_until(self, reply_type: int, timeout: float) -> bytes:
        loop = asyncio.get_running_loop()
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            try:
                data = await asyncio.wait_for(loop.sock_recv(self._sock, 4096), remaining)
            except TimeoutError:
                raise  # TimeoutError subclasses OSError: let request() retry
            except OSError as err:
                raise RfcommUnreachable(str(err)) from err
            if not data:
                raise RfcommUnreachable("connection closed by speaker")
            frame = _find_reply(data, reply_type)
            if frame is not None:
                return frame

    def close(self) -> None:
        """Close the socket."""
        self._sock.close()


def _find_reply(data: bytes, reply_type: int) -> bytes | None:
    """Pick the ``reply_type`` reply out of a read that may hold several frames.

    The protocol has no length prefix, so replies are located by their
    ``[type, 0x02]`` header; known fixed-size replies are cut to size.
    """
    i = 0
    while i + 1 < len(data):
        if data[i] == reply_type and data[i + 1] == proto.REPLY_OP:
            return data[i : i + proto.REPLY_SIZES.get(reply_type, len(data) - i)]
        i += proto.REPLY_SIZES.get(data[i], len(data) - i) if data[i + 1] == proto.REPLY_OP else 1
    return None


async def open_link(
    mac: str,
    channel: int = RFCOMM_CHANNEL,
    *,
    connector: Connector = _default_connector,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    busy_retries: int = BUSY_RETRIES,
) -> RfcommLink:
    """Connect to the speaker and return a link; raises typed errors.

    Reconnecting right after a close can fail with EBUSY while the previous
    RFCOMM channel is torn down (seen on hardware), so that is retried.
    """
    for attempt in range(busy_retries + 1):
        try:
            sock = await connector(mac, channel)
            return RfcommLink(sock)
        except RfcommError:
            raise
        except TimeoutError as err:
            raise RfcommUnreachable("connect timed out") from err
        except OSError as err:
            if err.errno == errno.EBUSY and attempt < busy_retries:
                await sleep(BUSY_BACKOFF)
                continue
            if err.errno in _UNAVAILABLE_ERRNOS:
                raise RfcommUnavailable(str(err)) from err
            raise RfcommUnreachable(str(err)) from err
    raise RfcommUnreachable("unreachable")  # pragma: no cover
