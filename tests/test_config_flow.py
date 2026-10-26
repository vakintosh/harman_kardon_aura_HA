"""Config flow tests: Wi-Fi setup plus the optional Bluetooth step."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hkaura_plus.const import (
    CONF_BT_MAC,
    CONF_WAKE_TIMEOUT,
    DOMAIN,
)
from custom_components.hkaura_plus.hk_bt_protocol import ProtocolError
from custom_components.hkaura_plus.rfcomm import RfcommUnavailable, RfcommUnreachable

MAC = "B8:69:C2:15:29:FD"
WIFI = {CONF_HOST: "172.16.1.102", CONF_PORT: 10025}
CF = "custom_components.hkaura_plus.config_flow"


@pytest.fixture(autouse=True)
def wifi_ok_and_no_setup():
    with (
        patch(f"{CF}.HKAuraPlusConfigFlow._test_connection", AsyncMock(return_value=True)),
        patch("custom_components.hkaura_plus.async_setup_entry", AsyncMock(return_value=True)),
    ):
        yield


async def _to_bluetooth_step(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], WIFI)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth"
    return result


async def test_skip_bluetooth_creates_wifi_only_entry(hass):
    result = await _to_bluetooth_step(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_BT_MAC not in result["data"]
    assert result["data"][CONF_HOST] == "172.16.1.102"


async def test_bluetooth_mac_is_probed_and_stored(hass):
    result = await _to_bluetooth_step(hass)
    with (
        patch(f"{CF}.rfcomm_supported", return_value=True),
        patch(f"{CF}.BluetoothSpeaker.power_state", AsyncMock(return_value=False)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BT_MAC: "b8-69-c2-15-29-fd"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_BT_MAC] == MAC  # normalised
    assert result["data"][CONF_WAKE_TIMEOUT] == 60


@pytest.mark.parametrize(
    ("supported", "probe", "mac", "error"),
    [
        (False, None, MAC, "bluetooth_unsupported"),
        (True, RfcommUnavailable("no adapter"), MAC, "bluetooth_unsupported"),
        (True, RfcommUnreachable("no reply"), MAC, "bluetooth_unreachable"),
        (True, ProtocolError("garbled"), MAC, "bluetooth_unreachable"),
        (True, None, "not-a-mac", "invalid_mac"),
    ],
)
async def test_bluetooth_errors_keep_form_open(hass, supported, probe, mac, error):
    result = await _to_bluetooth_step(hass)
    power = AsyncMock(side_effect=probe) if probe else AsyncMock(return_value=True)
    with (
        patch(f"{CF}.rfcomm_supported", return_value=supported),
        patch(f"{CF}.BluetoothSpeaker.power_state", power),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_BT_MAC: mac}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_BT_MAC: error}
    # user can still skip Bluetooth afterwards
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_BT_MAC not in result["data"]


async def test_reconfigure_can_add_bluetooth(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=WIFI, title="HK Aura Plus")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    with (
        patch(f"{CF}.rfcomm_supported", return_value=True),
        patch(f"{CF}.BluetoothSpeaker.power_state", AsyncMock(return_value=True)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**WIFI, CONF_BT_MAC: MAC, CONF_WAKE_TIMEOUT: 90},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_BT_MAC] == MAC
    assert entry.data[CONF_WAKE_TIMEOUT] == 90


async def test_reconfigure_adding_bluetooth_works_while_wifi_is_down(hass):
    """Standby has no Wi-Fi; unchanged host/port must not be re-tested."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=WIFI, title="HK Aura Plus")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with (
        patch(f"{CF}.HKAuraPlusConfigFlow._test_connection", AsyncMock(return_value=False)) as wifi,
        patch(f"{CF}.rfcomm_supported", return_value=True),
        patch(f"{CF}.BluetoothSpeaker.power_state", AsyncMock(return_value=False)),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**WIFI, CONF_BT_MAC: MAC}
        )
    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_BT_MAC] == MAC
    wifi.assert_not_awaited()


async def test_reconfigure_changed_host_still_requires_wifi(hass):
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(domain=DOMAIN, data=WIFI, title="HK Aura Plus")
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    with patch(
        f"{CF}.HKAuraPlusConfigFlow._test_connection", AsyncMock(return_value=False)
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "10.0.0.9", CONF_PORT: 10025}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
