"""Setup, entities and service with Bluetooth mocked."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hkaura_plus.const import CONF_BT_MAC, CONF_WAKE_TIMEOUT, DOMAIN
from custom_components.hkaura_plus.hk_bt_device import BluetoothSpeaker, BtStatus, WakeFailed, WakeResult
from custom_components.hkaura_plus.hk_bt_protocol import Source
from custom_components.hkaura_plus.rfcomm import RfcommUnreachable

MAC = "B8:69:C2:15:29:FD"
WIFI = {CONF_HOST: "172.16.1.102", CONF_PORT: 10025}
BT = {**WIFI, CONF_BT_MAC: MAC, CONF_WAKE_TIMEOUT: 60}
ON = BtStatus(power=True, source=Source.AIRPLAY)
STANDBY = BtStatus(power=False, source=None)


@pytest.fixture(autouse=True)
def no_wifi_traffic():
    with (
        patch("custom_components.hkaura_plus.speaker.HKDevice.send_request", AsyncMock()),
        patch("custom_components.hkaura_plus.speaker.HKDevice.async_port_open", AsyncMock(return_value=True)),
    ):
        yield


async def setup_entry(hass, data, status=ON):
    entry = MockConfigEntry(domain=DOMAIN, data=data, title="HK Aura Plus")
    entry.add_to_hass(hass)
    side = status if isinstance(status, Exception) else None
    with patch.object(
        BluetoothSpeaker, "status",
        AsyncMock(side_effect=side, return_value=None if side else status),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


def entity_id(hass, domain, key):
    reg = er.async_get(hass)
    return next(
        e.entity_id for e in reg.entities.values()
        if e.platform == DOMAIN and e.domain == domain and e.unique_id.endswith(key)
    )


async def test_wifi_only_entry_has_no_bluetooth_entities(hass):
    entry = await setup_entry(hass, WIFI)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.coordinator is None
    reg = er.async_get(hass)
    domains = {e.domain for e in reg.entities.values() if e.platform == DOMAIN}
    assert "select" not in domains and "binary_sensor" not in domains
    assert not any(e.unique_id.endswith("_wake") for e in reg.entities.values())
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "wake", {}, blocking=True)


async def test_awake_state(hass):
    await setup_entry(hass, BT, ON)
    assert hass.states.get(entity_id(hass, "binary_sensor", "bt_power")).state == STATE_ON
    assert hass.states.get(entity_id(hass, "select", "source")).state == "airplay"


async def test_standby_state(hass):
    await setup_entry(hass, BT, STANDBY)
    assert hass.states.get(entity_id(hass, "binary_sensor", "bt_power")).state == STATE_OFF
    assert hass.states.get(entity_id(hass, "select", "source")).state == STATE_UNKNOWN


async def test_bluetooth_failure_does_not_break_setup(hass):
    entry = await setup_entry(hass, BT, RfcommUnreachable("down"))
    assert entry.state is ConfigEntryState.LOADED  # Wi-Fi side unaffected
    assert hass.states.get(entity_id(hass, "binary_sensor", "bt_power")).state == STATE_UNAVAILABLE
    # Wi-Fi entities still exist
    assert hass.states.get(entity_id(hass, "button", "power_off")) is not None


async def test_wake_service_uses_configured_timeout(hass):
    await setup_entry(hass, {**BT, CONF_WAKE_TIMEOUT: 90}, STANDBY)
    wake = AsyncMock(return_value=WakeResult.WOKE)
    with (
        patch.object(BluetoothSpeaker, "wake", wake),
        patch.object(BluetoothSpeaker, "status", AsyncMock(return_value=ON)),
    ):
        await hass.services.async_call(DOMAIN, "wake", {}, blocking=True)
        await hass.services.async_call(DOMAIN, "wake", {"timeout": 15}, blocking=True)
    assert wake.await_args_list[0].kwargs["port_wait"] == 90
    assert wake.await_args_list[1].kwargs["port_wait"] == 15
    assert wake.await_args_list[0].kwargs["port_ready"] is not None


async def test_wake_button_and_failure_mapping(hass):
    await setup_entry(hass, BT, STANDBY)
    eid = entity_id(hass, "button", "_wake")
    with (
        patch.object(BluetoothSpeaker, "wake", AsyncMock(return_value=WakeResult.WOKE)) as wake,
        patch.object(BluetoothSpeaker, "status", AsyncMock(return_value=ON)),
    ):
        await hass.services.async_call("button", "press", {"entity_id": eid}, blocking=True)
        wake.assert_awaited_once()
    with patch.object(BluetoothSpeaker, "wake", AsyncMock(side_effect=WakeFailed("no"))):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call("button", "press", {"entity_id": eid}, blocking=True)


async def test_select_source_and_standby_guard(hass):
    await setup_entry(hass, BT, ON)
    eid = entity_id(hass, "select", "source")
    setter = AsyncMock()
    with (
        patch.object(BluetoothSpeaker, "set_source", setter),
        patch.object(BluetoothSpeaker, "status", AsyncMock(return_value=ON)),
    ):
        await hass.services.async_call(
            "select", "select_option", {"entity_id": eid, "option": "aux"}, blocking=True
        )
    setter.assert_awaited_once_with(Source.AUX)

    # standby: refuse instead of sending a command to a sleeping speaker
    with patch.object(BluetoothSpeaker, "status", AsyncMock(return_value=STANDBY)):
        coord = hass.config_entries.async_entries(DOMAIN)[0].runtime_data.coordinator
        await coord.async_refresh()
    with patch.object(BluetoothSpeaker, "set_source", setter):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "select", "select_option", {"entity_id": eid, "option": "aux"}, blocking=True
            )
