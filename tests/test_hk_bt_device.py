"""Wake guard tests with a fake link (no Bluetooth)."""
import pytest

from custom_components.hkaura_plus import hk_bt_protocol as p
from custom_components.hkaura_plus import hk_bt_device as dev
from custom_components.hkaura_plus.rfcomm import RfcommUnreachable


class FakeLink:
    """Answers power queries from a script; records everything sent."""

    def __init__(self, power_replies):
        self.power_replies = list(power_replies)  # each: bytes | Exception
        self.source_reply = b"\x0e\x02\x01"  # airplay
        self.sent = []
        self.closed = False

    async def request(self, frame, reply_type, *, timeout=3.0, retries=2):
        self.sent.append(frame)
        if frame == p.QUERY_SOURCE:
            return self.source_reply
        assert frame == p.QUERY_POWER
        r = self.power_replies.pop(0) if len(self.power_replies) > 1 else self.power_replies[0]
        if isinstance(r, Exception):
            raise r
        return r

    async def send(self, frame):
        self.sent.append(frame)

    def close(self):
        self.closed = True


def speaker_with(link):
    async def opener(mac, channel=2, **_):
        return link

    return dev.BluetoothSpeaker("AA:BB:CC:DD:EE:FF", opener=opener, sleep=_nosleep)


async def _nosleep(_):
    return None


ON, OFF = b"\x0b\x02\x01", b"\x0b\x02\x00"


async def test_power_state_reads_and_closes():
    link = FakeLink([ON])
    assert await speaker_with(link).power_state() is True
    assert link.closed


async def test_wake_when_already_on_sends_nothing():
    link = FakeLink([ON])
    result = await speaker_with(link).wake()
    assert result is dev.WakeResult.ALREADY_ON
    assert p.POWER_TOGGLE not in link.sent


async def test_wake_from_standby_sends_toggle_once_and_confirms():
    link = FakeLink([OFF, OFF, ON])  # initial read, 1st poll still off, 2nd on
    result = await speaker_with(link).wake()
    assert result is dev.WakeResult.WOKE
    assert link.sent.count(p.POWER_TOGGLE) == 1
    assert link.sent[0] == p.QUERY_POWER  # state read BEFORE the toggle
    assert link.sent.index(p.POWER_TOGGLE) == 1


async def test_wake_never_resends_toggle_if_not_confirmed():
    link = FakeLink([OFF])  # stays off forever
    with pytest.raises(dev.WakeFailed):
        await speaker_with(link).wake(confirm_attempts=3)
    assert link.sent.count(p.POWER_TOGGLE) == 1


async def test_wake_sends_nothing_if_state_unknown():
    link = FakeLink([RfcommUnreachable("no reply")])
    with pytest.raises(RfcommUnreachable):
        await speaker_with(link).wake()
    assert p.POWER_TOGGLE not in link.sent
    assert link.closed


async def test_wake_sends_nothing_on_garbled_state():
    link = FakeLink([b"\x0b\x02"])  # too short to decode
    with pytest.raises(p.ProtocolError):
        await speaker_with(link).wake()
    assert p.POWER_TOGGLE not in link.sent


async def test_wake_waits_for_port_when_given():
    link = FakeLink([OFF, ON])
    calls = []

    async def port_ready():
        calls.append(1)
        return len(calls) >= 2

    result = await speaker_with(link).wake(port_ready=port_ready, port_wait=5)
    assert result is dev.WakeResult.WOKE
    assert len(calls) == 2


async def test_wake_port_never_ready_raises():
    link = FakeLink([OFF, ON])

    async def never():
        return False

    with pytest.raises(dev.WakeFailed):
        await speaker_with(link).wake(port_ready=never, port_wait=2)


def test_default_port_wait_is_120_seconds():
    """Measured boot-to-control-port: 25-32 s typical, 58.4 s worst seen."""
    assert dev.DEFAULT_PORT_WAIT == 120
    import inspect
    sig = inspect.signature(dev.BluetoothSpeaker.wake)
    assert sig.parameters["port_wait"].default == dev.DEFAULT_PORT_WAIT


async def test_port_wait_is_in_seconds_and_configurable():
    link = FakeLink([OFF, ON])
    calls = []

    async def never():
        calls.append(1)
        return False

    with pytest.raises(dev.WakeFailed):
        await speaker_with(link).wake(port_ready=never, port_wait=7)
    assert len(calls) == 7  # 1s poll interval


async def test_status_awake_includes_source():
    link = FakeLink([ON])
    st = await speaker_with(link).status()
    assert st == dev.BtStatus(power=True, source=p.Source.AIRPLAY)
    assert link.closed


async def test_status_standby_skips_source():
    link = FakeLink([OFF])
    st = await speaker_with(link).status()
    assert st == dev.BtStatus(power=False, source=None)
    assert p.QUERY_SOURCE not in link.sent


async def test_default_request_timeout_is_short_enough_for_dropped_first_query():
    """In standby the first query is always dropped; a 3 s wait made each read ~3.8 s."""
    import inspect
    from custom_components.hkaura_plus.rfcomm import RfcommLink
    sig = inspect.signature(RfcommLink.request)
    assert sig.parameters["timeout"].default <= 1.5
    assert sig.parameters["retries"].default >= 3


async def test_already_on_still_waits_for_wifi_port():
    """Plug restored -> speaker reports on while Wi-Fi is still booting."""
    link = FakeLink([ON])
    calls = []

    async def port_ready():
        calls.append(1)
        return len(calls) >= 3

    result = await speaker_with(link).wake(port_ready=port_ready, port_wait=10)
    assert result is dev.WakeResult.ALREADY_ON
    assert len(calls) == 3
    assert p.POWER_TOGGLE not in link.sent  # still never toggles an awake speaker


async def test_already_on_port_never_ready_raises():
    link = FakeLink([ON])

    async def never():
        return False

    with pytest.raises(dev.WakeFailed):
        await speaker_with(link).wake(port_ready=never, port_wait=2)
    assert p.POWER_TOGGLE not in link.sent
