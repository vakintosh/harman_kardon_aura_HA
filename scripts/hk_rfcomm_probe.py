#!/usr/bin/env python3
"""READ-ONLY probe of the HK Aura Plus Bluetooth SPP (RFCOMM) control channel.

THROWAWAY SPIKE. Protocol recovered from the HK Remote 4.5 APK
(com.harman.hkremote.device.bt.util.BluetoothUtilHelper). Only query
commands are sent; nothing here can change speaker state.

Transports
  Linux / Raspberry Pi:  --mac B8:69:C2:15:29:FD [--channel 2]
  macOS:                 --tty /dev/cu.<paired-speaker-name>   (pair first)

Run once with the speaker awake and once in standby, then compare output.
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import time

# Whitelist: query-only frames (type, op=1 ...). Never add SET_* here.
QUERIES = {
    "capability": bytes([0x00, 0x01]),
    "eq_mode": bytes([0x01, 0x01]),
    "volume_mute": bytes([0x02, 0x01]),
    "name": bytes([0x04, 0x01]),
    "version": bytes([0x06, 0x01]),
    "power_status": bytes([0x0B, 0x01]),
    "series_id": bytes([0x0C, 0x01]),
    "source": bytes([0x0E, 0x01]),
    "battery": bytes([0x0F, 0x01]),
}
TYPE_NAMES = {0: "capability", 1: "eq_mode", 2: "volume_mute", 3: "wifi", 4: "name",
              5: "upgrade", 6: "version", 7: "room_eq", 11: "power_status",
              12: "series_id", 13: "eq_setting", 14: "source", 15: "battery"}
SOURCES = {0: "dock", 1: "airplay", 2: "bluetooth", 3: "aux", 4: "optical",
           5: "phono", 6: "dlna", 7: "tv"}


def decode(frame: bytes) -> str:
    """Best-effort decode based on the APK parsers (unverified on hardware)."""
    if not frame:
        return "<empty>"
    t = frame[0]
    label = TYPE_NAMES.get(t, f"type{t}")
    if t == 2 and len(frame) >= 4:
        return f"{label}: mute={frame[2]} volume={frame[3]}"
    if t == 11 and len(frame) >= 3:
        return f"{label}: byte2={frame[2]} (APK: 0 => 'power off', 1 => 'on')"
    if t == 14 and len(frame) >= 3:
        return f"{label}: {SOURCES.get(frame[2], frame[2])}"
    if t == 4:
        return f"{label}: {frame[2:].decode('utf-8', 'replace')!r}"
    if t == 1 and len(frame) >= 3:
        return f"{label}: mode={frame[2]}"
    return f"{label}: raw"


class Link:
    def __init__(self, mac: str | None, channel: int, tty: str | None, timeout: float):
        self.timeout = timeout
        self.sock = None
        self.fd = None
        if tty:
            import termios
            import tty as ttymod
            self.fd = os.open(tty, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
            ttymod.setraw(self.fd)
            termios.tcflush(self.fd, termios.TCIOFLUSH)
        else:
            self.sock = socket.socket(
                socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            self.sock.settimeout(10)
            self.sock.connect((mac, channel))
            self.sock.settimeout(timeout)

    def send(self, data: bytes) -> None:
        if self.sock:
            self.sock.sendall(data)
        else:
            os.write(self.fd, data)

    def recv(self) -> bytes:
        if self.sock:
            try:
                return self.sock.recv(4096)
            except socket.timeout:
                return b""
        import select
        r, _, _ = select.select([self.fd], [], [], self.timeout)
        return os.read(self.fd, 4096) if r else b""

    def close(self) -> None:
        if self.sock:
            self.sock.close()
        if self.fd is not None:
            os.close(self.fd)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mac")
    ap.add_argument("--channel", type=int, default=2,
                    help="RFCOMM channel (btmon SDP: Serial Port 0x1101 = 2)")
    ap.add_argument("--tty", help="macOS serial device for the paired speaker")
    ap.add_argument("--timeout", type=float, default=2.0)
    ap.add_argument("--only", nargs="*", choices=sorted(QUERIES),
                    help="subset of queries (default: all)")
    a = ap.parse_args()
    if not (a.mac or a.tty):
        ap.error("need --mac (Linux) or --tty (macOS)")

    t0 = time.time()
    try:
        link = Link(a.mac, a.channel, a.tty, a.timeout)
    except OSError as e:
        print(f"CONNECT FAILED after {time.time()-t0:.1f}s: {e!r}")
        return 2
    print(f"CONNECTED in {time.time()-t0:.1f}s")
    try:
        for name in a.only or QUERIES:
            req = QUERIES[name]
            link.send(req)
            resp = link.recv()
            print(f"{name:13} tx={req.hex(' ')}  rx={resp.hex(' ') or '<none>'}"
                  f"  -> {decode(resp) if resp else 'no reply'}")
    finally:
        link.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
