"""Bluetooth state coordinator and wake helper for HK Aura Plus."""
from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BT_POLL_INTERVAL, DOMAIN
from .hk_bt_device import BluetoothSpeaker, BtStatus, WakeFailed, WakeResult
from .hk_bt_protocol import ProtocolError
from .rfcomm import RfcommError
from .speaker import HKDevice

_LOGGER = logging.getLogger(__name__)


class HKAuraBtCoordinator(DataUpdateCoordinator[BtStatus]):
    """Poll power/source over Bluetooth; works while Wi-Fi is down."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        bluetooth: BluetoothSpeaker,
        device: HKDevice,
        wake_timeout: float,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} bluetooth",
            update_interval=timedelta(seconds=BT_POLL_INTERVAL),
        )
        self.bluetooth = bluetooth
        self.device = device
        self.wake_timeout = wake_timeout

    async def _async_update_data(self) -> BtStatus:
        try:
            return await self.bluetooth.status()
        except (RfcommError, ProtocolError) as err:
            raise UpdateFailed(f"Bluetooth status failed: {err}") from err

    async def async_wake(self, timeout: float | None = None) -> WakeResult:
        """Wake the speaker (guarded) and wait for the Wi-Fi control port."""
        started = time.monotonic()
        try:
            result = await self.bluetooth.wake(
                port_ready=self.device.async_port_open,
                port_wait=self.wake_timeout if timeout is None else timeout,
            )
        except (RfcommError, ProtocolError, WakeFailed) as err:
            _LOGGER.warning(
                "Wake failed after %.1fs: %s: %s",
                time.monotonic() - started,
                type(err).__name__,
                err,
            )
            raise HomeAssistantError(f"Could not wake speaker: {err}") from err
        _LOGGER.info(
            "Wake result: %s (Wi-Fi port open after %.1fs)",
            result.name,
            time.monotonic() - started,
        )
        await self.async_request_refresh()
        return result
