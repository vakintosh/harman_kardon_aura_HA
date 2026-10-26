"""Live tests against a real speaker. Opt-in; run on a host with Bluetooth.

  HK_LIVE_MAC=B8:69:C2:15:29:FD pytest tests/live -v          # read-only
  HK_LIVE_WAKE=1 HK_LIVE_HOST=172.16.1.102 ...                # also wake test
                                                              # (speaker must be in standby)
The Bluetooth modules are loaded via a stub package so Home Assistant is not
needed on the test host.
"""
import asyncio
import importlib
import os
import pathlib
import sys
import time
import types

import pytest

MAC = os.environ.get("HK_LIVE_MAC")
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not MAC, reason="set HK_LIVE_MAC to run live tests"),
]

_SRC = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "hkaura_plus"
_pkg = types.ModuleType("hkbt")
_pkg.__path__ = [str(_SRC)]
sys.modules.setdefault("hkbt", _pkg)
proto = importlib.import_module("hkbt.hk_bt_protocol")
rfcomm = importlib.import_module("hkbt.rfcomm")
device = importlib.import_module("hkbt.hk_bt_device")


@pytest.fixture
def speaker():
    return device.BluetoothSpeaker(MAC)


def test_host_supports_rfcomm():
    assert rfcomm.rfcomm_supported()


async def test_power_state_is_bool(speaker):
    assert isinstance(await speaker.power_state(), bool)


async def test_cold_connect_then_query_round_trip(speaker):
    t0 = time.monotonic()
    link = await rfcomm.open_link(MAC)
    try:
        reply = await link.request(proto.QUERY_VOLUME_MUTE, proto.TYPE_VOLUME_MUTE)
    finally:
        link.close()
    vm = proto.decode_volume_mute(reply)
    assert 0 <= vm.volume <= 100
    print(f"connect+query {time.monotonic() - t0:.1f}s volume={vm.volume}")


async def test_source_and_name_when_awake(speaker):
    if not await speaker.power_state():
        pytest.skip("speaker in standby; name/source are not meaningful")
    assert isinstance(await speaker.source(), proto.Source)


async def test_wake_is_noop_when_already_on(speaker):
    if not await speaker.power_state():
        pytest.skip("speaker in standby")
    assert await speaker.wake() is device.WakeResult.ALREADY_ON
    assert await speaker.power_state() is True  # still on: nothing was toggled


@pytest.mark.skipif(not os.environ.get("HK_LIVE_WAKE"), reason="set HK_LIVE_WAKE=1")
async def test_wake_from_standby(speaker):
    if await speaker.power_state():
        pytest.skip("speaker already on; put it in standby for this test")
    host = os.environ.get("HK_LIVE_HOST")

    async def port_ready():
        if not host:
            return True
        try:
            _, w = await asyncio.wait_for(asyncio.open_connection(host, 10025), 2)
        except OSError:
            return False
        w.close()
        return True

    t0 = time.monotonic()
    assert await speaker.wake(port_ready=port_ready) is device.WakeResult.WOKE
    print(f"wake to port-ready {time.monotonic() - t0:.1f}s")
    assert await speaker.power_state() is True
