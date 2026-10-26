"""Transport tests: fake speaker over a socketpair (no Bluetooth needed)."""
import asyncio
import errno
import socket

import pytest

from custom_components.hkaura_plus import hk_bt_protocol as p
from custom_components.hkaura_plus import rfcomm


def make_pair():
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    return a, b


async def fake_speaker(sock, script):
    """script: list of reply bytes (or None to stay silent) per received request."""
    loop = asyncio.get_running_loop()
    received = []
    for reply in script:
        req = await loop.sock_recv(sock, 64)
        received.append(req)
        if reply is not None:
            await loop.sock_sendall(sock, reply)
    return received


async def test_request_returns_matching_reply():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    task = asyncio.create_task(fake_speaker(b, [b"\x0b\x02\x01"]))
    reply = await link.request(p.QUERY_POWER, p.TYPE_POWER, timeout=1, retries=0)
    assert reply == b"\x0b\x02\x01"
    assert await task == [p.QUERY_POWER]
    link.close()


async def test_dropped_first_query_is_retried():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    task = asyncio.create_task(fake_speaker(b, [None, b"\x0b\x02\x00"]))
    reply = await link.request(p.QUERY_POWER, p.TYPE_POWER, timeout=0.2, retries=2)
    assert p.decode_power(reply) is False
    assert await task == [p.QUERY_POWER, p.QUERY_POWER]
    link.close()


async def test_unrelated_frames_are_skipped():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    task = asyncio.create_task(
        fake_speaker(b, [b"\x02\x02\x00\x14" + b"\x0b\x02\x01"])
    )
    reply = await link.request(p.QUERY_POWER, p.TYPE_POWER, timeout=1, retries=0)
    assert reply == b"\x0b\x02\x01"
    await task
    link.close()


async def test_timeout_after_retries_raises_unreachable():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    task = asyncio.create_task(fake_speaker(b, [None, None]))
    with pytest.raises(rfcomm.RfcommUnreachable):
        await link.request(p.QUERY_POWER, p.TYPE_POWER, timeout=0.1, retries=1)
    await task
    link.close()


async def test_peer_close_raises_unreachable():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    b.close()
    with pytest.raises(rfcomm.RfcommUnreachable):
        await link.request(p.QUERY_POWER, p.TYPE_POWER, timeout=0.2, retries=0)
    link.close()


async def test_send_does_not_wait_for_reply():
    a, b = make_pair()
    link = rfcomm.RfcommLink(a)
    await link.send(p.POWER_TOGGLE)
    assert await asyncio.get_running_loop().sock_recv(b, 16) == p.POWER_TOGGLE
    link.close()


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (OSError(errno.EHOSTDOWN, "down"), rfcomm.RfcommUnreachable),
        (OSError(errno.ECONNREFUSED, "refused"), rfcomm.RfcommUnreachable),
        (OSError(errno.ETIMEDOUT, "timeout"), rfcomm.RfcommUnreachable),
        (OSError(errno.ENODEV, "no adapter"), rfcomm.RfcommUnavailable),
        (OSError(errno.EAFNOSUPPORT, "no bt"), rfcomm.RfcommUnavailable),
        (OSError(errno.EPERM, "denied"), rfcomm.RfcommUnavailable),
    ],
)
async def test_connect_errors_are_typed(exc, expected):
    async def boom(mac, channel):
        raise exc

    with pytest.raises(expected):
        await rfcomm.open_link("AA:BB:CC:DD:EE:FF", connector=boom)


async def test_open_link_uses_connector_and_wraps_socket():
    a, b = make_pair()

    async def ok(mac, channel):
        assert (mac, channel) == ("AA:BB:CC:DD:EE:FF", 2)
        return a

    link = await rfcomm.open_link("AA:BB:CC:DD:EE:FF", connector=ok)
    assert isinstance(link, rfcomm.RfcommLink)
    link.close()
    b.close()


def test_rfcomm_supported_reflects_platform():
    assert rfcomm.rfcomm_supported() is hasattr(socket, "AF_BLUETOOTH")


async def test_connect_retries_while_previous_channel_is_busy():
    """Live finding: reconnecting right after close gives EBUSY for a moment."""
    a, b = make_pair()
    attempts = []

    async def flaky(mac, channel):
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError(errno.EBUSY, "Device or resource busy")
        return a

    async def nosleep(_):
        return None

    link = await rfcomm.open_link("AA:BB:CC:DD:EE:FF", connector=flaky, sleep=nosleep)
    assert len(attempts) == 3
    link.close()
    b.close()


async def test_connect_gives_up_after_busy_retries():
    async def always_busy(mac, channel):
        raise OSError(errno.EBUSY, "Device or resource busy")

    async def nosleep(_):
        return None

    with pytest.raises(rfcomm.RfcommUnreachable):
        await rfcomm.open_link(
            "AA:BB:CC:DD:EE:FF", connector=always_busy, sleep=nosleep, busy_retries=2
        )
