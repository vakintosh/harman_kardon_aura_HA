"""Pure codec for the HK Aura Plus Bluetooth (RFCOMM/SPP) control protocol.

Recovered from the HK Remote 4.5 APK (BluetoothUtilHelper) and verified on
hardware. Requests are ``[type, op, ...]``; replies are ``[type, 0x02, payload]``.
No I/O happens here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Final

REPLY_OP: Final = 0x02

TYPE_EQ_MODE: Final = 0x01
TYPE_VOLUME_MUTE: Final = 0x02
TYPE_NAME: Final = 0x04
TYPE_POWER: Final = 0x0B
TYPE_SOURCE: Final = 0x0E

QUERY_EQ_MODE: Final = bytes([TYPE_EQ_MODE, 0x01])
QUERY_VOLUME_MUTE: Final = bytes([TYPE_VOLUME_MUTE, 0x01])
QUERY_NAME: Final = bytes([TYPE_NAME, 0x01])
QUERY_POWER: Final = bytes([TYPE_POWER, 0x01])
QUERY_SOURCE: Final = bytes([TYPE_SOURCE, 0x01])

# Fixed reply sizes (bytes, incl. header) for types we decode; used to split
# multi-frame reads. Name is variable length so it is deliberately absent.
REPLY_SIZES: Final = {TYPE_EQ_MODE: 3, TYPE_VOLUME_MUTE: 4, TYPE_POWER: 3, TYPE_SOURCE: 3}

# The app sends identical bytes for power ON and OFF: this is a toggle.
POWER_TOGGLE: Final = bytes([TYPE_POWER, 0x03, 0x00, 0x20])


class ProtocolError(ValueError):
    """Raised when a frame is not a valid reply of the expected type."""


class Source(IntEnum):
    """Input source codes (APK SOURCE_* constants)."""

    DOCK = 0
    AIRPLAY = 1
    BLUETOOTH = 2
    AUX = 3
    OPTICAL = 4
    PHONO = 5
    DLNA = 6
    TV = 7


@dataclass(frozen=True, slots=True)
class VolumeMute:
    """Decoded volume/mute reply."""

    muted: bool
    volume: int


def is_reply(frame: bytes, frame_type: int) -> bool:
    """Return True if ``frame`` is a reply of ``frame_type``."""
    return len(frame) >= 2 and frame[0] == frame_type and frame[1] == REPLY_OP


def _payload(frame: bytes, frame_type: int, min_payload: int) -> bytes:
    if not is_reply(frame, frame_type):
        raise ProtocolError(f"not a type {frame_type:#04x} reply: {frame.hex(' ')}")
    payload = frame[2:]
    if len(payload) < min_payload:
        raise ProtocolError(f"short reply: {frame.hex(' ')}")
    return payload


def decode_power(frame: bytes) -> bool:
    """Return True when the speaker is on (payload 1), False in standby (0)."""
    return _payload(frame, TYPE_POWER, 1)[0] == 1


def decode_volume_mute(frame: bytes) -> VolumeMute:
    """Decode a volume/mute reply."""
    payload = _payload(frame, TYPE_VOLUME_MUTE, 2)
    return VolumeMute(muted=payload[0] != 0, volume=payload[1])


def decode_source(frame: bytes) -> Source:
    """Decode the current source."""
    try:
        return Source(_payload(frame, TYPE_SOURCE, 1)[0])
    except ValueError as err:
        raise ProtocolError(f"unknown source in {frame.hex(' ')}") from err


def decode_name(frame: bytes) -> str:
    """Decode the length-prefixed device name."""
    payload = _payload(frame, TYPE_NAME, 1)
    return payload[1 : 1 + payload[0]].decode("utf-8", "replace")


def decode_eq_mode(frame: bytes) -> int:
    """Decode the EQ mode code."""
    return _payload(frame, TYPE_EQ_MODE, 1)[0]
