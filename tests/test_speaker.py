"""Wi-Fi XML client: transient connect failures are retried, commands are not duplicated."""
import errno
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hkaura_plus import speaker


def fake_conn():
    reader = MagicMock()
    reader.read = AsyncMock(return_value=b"")
    writer = MagicMock()
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return reader, writer


@pytest.fixture(autouse=True)
def no_backoff():
    with patch.object(speaker, "_sleep", AsyncMock()) as sleep:
        yield sleep


async def test_retries_transient_connect_error_then_sends_once():
    reader, writer = fake_conn()
    calls = []

    async def flaky(host, port):
        calls.append(1)
        if len(calls) < 3:
            raise OSError(errno.EHOSTUNREACH, "No route to host")
        return reader, writer

    with patch("asyncio.open_connection", flaky):
        dev = speaker.HKDevice("172.16.1.102")
        await dev.send_request("power-off")
    assert len(calls) == 3
    assert writer.write.call_count == 1  # the command itself is never sent twice
    assert dev.available is True


async def test_gives_up_after_retries_and_marks_unavailable():
    attempts = []

    async def always_down(host, port):
        attempts.append(1)
        raise OSError(errno.EHOSTUNREACH, "No route to host")

    with patch("asyncio.open_connection", always_down):
        dev = speaker.HKDevice("172.16.1.102")
        with pytest.raises(OSError):
            await dev.send_request("power-off")
    assert len(attempts) == speaker.CONNECT_RETRIES + 1
    assert dev.available is False


async def test_timeout_on_connect_is_retried():
    reader, writer = fake_conn()
    calls = []

    async def slow_then_ok(host, port):
        calls.append(1)
        if len(calls) == 1:
            raise TimeoutError
        return reader, writer

    with patch("asyncio.open_connection", slow_then_ok):
        await speaker.HKDevice("172.16.1.102").send_request("mute-on")
    assert len(calls) == 2


async def test_unknown_action_is_rejected_without_connecting():
    with patch("asyncio.open_connection", AsyncMock()) as conn:
        with pytest.raises(ValueError):
            await speaker.HKDevice("172.16.1.102").send_request("nope")
    conn.assert_not_called()
