"""BLE connection manager for Bookoo devices."""
import asyncio
import logging
from typing import Callable, Optional, List, Any
from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .constants import (
    DEVICE_NAME_PREFIX,
    SERVICE_UUID,
    CHAR_COMMAND_UUID,
    CHAR_NOTIFY_DESCRIPTOR,
    RECONNECT_INTERVAL_SECONDS,
    SCAN_INTERVAL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class BookooBLEManager:
    """Manages BLE connection to Bookoo device."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        """Initialize the BLE manager."""
        self.hass = hass
        self.address = address
        self.client: Optional[BleakClient] = None
        self.device: Optional[BLEDevice] = None
        self._notification_callback: Optional[Callable[[bytes], None]] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._notification_task: Optional[asyncio.Task] = None
        self._connected = False
        self._should_reconnect = True
        self._reconnect_interval = RECONNECT_INTERVAL_SECONDS

    @property
    def is_connected(self) -> bool:
        """Return true if connected to device."""
        return self._connected and self.client and self.client.is_connected

    async def async_start(self) -> bool:
        """Start the BLE manager and connect to device."""
        self._should_reconnect = True
        return await self._async_connect()

    async def async_stop(self) -> None:
        """Stop the BLE manager and disconnect."""
        self._should_reconnect = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None
        
        if self._notification_task:
            self._notification_task.cancel()
            self._notification_task = None
        
        await self._async_disconnect()

    async def _async_connect(self) -> bool:
        """Connect to the Bookoo device."""
        try:
            # Try to get device from HA's bluetooth integration first
            device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            
            if not device:
                _LOGGER.debug("Device not found in HA cache, scanning...")
                device = await self._async_scan_for_device()
            
            if not device:
                _LOGGER.error("Failed to find Bookoo device with address %s", self.address)
                return False
            
            self.device = device
            
            # Use HA's BLE client if available
            self.client = await bluetooth.async_get_client(self.hass, self.device)
            
            if not self.client:
                _LOGGER.debug("Creating new BLE client")
                self.client = BleakClient(self.device)
                await self.client.connect()
            
            self._connected = True
            _LOGGER.info("Connected to Bookoo device %s", self.address)
            
            # Start notifications
            await self._async_start_notifications()
            
            return True
            
        except Exception as ex:
            _LOGGER.error("Failed to connect to Bookoo device: %s", ex)
            self._connected = False
            
            if self._should_reconnect:
                await self._async_schedule_reconnect()
            
            return False

    async def _async_disconnect(self) -> None:
        """Disconnect from the device."""
        if self.client:
            try:
                await self._async_stop_notifications()
                if self.client.is_connected:
                    await self.client.disconnect()
            except Exception as ex:
                _LOGGER.debug("Error disconnecting: %s", ex)
            finally:
                self.client = None
                self._connected = False

    async def _async_scan_for_device(self) -> Optional[BLEDevice]:
        """Scan for Bookoo device."""
        try:
            # Use HA's scanner if available
            scanner = bluetooth.async_get_scanner(self.hass)
            
            if scanner:
                devices = await scanner.discover()
                for device in devices:
                    if device.address == self.address:
                        return device
                    if device.name and device.name.startswith(DEVICE_NAME_PREFIX):
                        if device.address.upper() == self.address.upper():
                            return device
            
            # Fallback to Bleak scanner
            devices = await BleakScanner.discover(timeout=SCAN_INTERVAL_SECONDS)
            for device in devices:
                if device.address == self.address:
                    return device
                if device.name and device.name.startswith(DEVICE_NAME_PREFIX):
                    if device.address.upper() == self.address.upper():
                        return device
            
            return None
            
        except Exception as ex:
            _LOGGER.error("Error scanning for devices: %s", ex)
            return None

    async def _async_start_notifications(self) -> None:
        """Start receiving notifications from the device."""
        if not self.client or not self.client.is_connected:
            return
        
        try:
            # Subscribe to notifications
            await self.client.start_notify(
                CHAR_COMMAND_UUID,
                self._notification_handler
            )
            _LOGGER.debug("Started notifications for %s", CHAR_COMMAND_UUID)
            
        except Exception as ex:
            _LOGGER.error("Failed to start notifications: %s", ex)

    async def _async_stop_notifications(self) -> None:
        """Stop receiving notifications from the device."""
        if not self.client:
            return
        
        try:
            await self.client.stop_notify(CHAR_COMMAND_UUID)
            _LOGGER.debug("Stopped notifications")
        except Exception as ex:
            _LOGGER.debug("Error stopping notifications: %s", ex)

    def _notification_handler(self, sender: int, data: bytes) -> None:
        """Handle notification from device."""
        _LOGGER.debug("Notification from %s: %s", sender, data.hex())
        
        if self._notification_callback:
            try:
                self._notification_callback(data)
            except Exception as ex:
                _LOGGER.error("Error in notification callback: %s", ex)

    def set_notification_callback(self, callback: Callable[[bytes], None]) -> None:
        """Set the callback for notifications."""
        self._notification_callback = callback

    async def async_write_command(self, command: bytes) -> bool:
        """Write a command to the device."""
        if not self.is_connected:
            _LOGGER.warning("Cannot write command: not connected")
            return False
        
        try:
            await self.client.write_gatt_char(CHAR_COMMAND_UUID, command)
            _LOGGER.debug("Wrote command: %s", command.hex())
            return True
        except Exception as ex:
            _LOGGER.error("Failed to write command: %s", ex)
            
            # Trigger reconnection on write failure
            if self._should_reconnect:
                await self._async_schedule_reconnect()
            
            return False

    async def _async_schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return
        
        self._reconnect_task = asyncio.create_task(self._async_reconnect_loop())

    async def _async_reconnect_loop(self) -> None:
        """Reconnection loop."""
        while self._should_reconnect and not self.is_connected:
            _LOGGER.debug("Attempting reconnection in %d seconds...", self._reconnect_interval)
            await asyncio.sleep(self._reconnect_interval)
            
            if not self._should_reconnect:
                break
            
            success = await self._async_connect()
            if success:
                self._reconnect_interval = RECONNECT_INTERVAL_SECONDS
            else:
                # Exponential backoff up to 5 minutes
                self._reconnect_interval = min(self._reconnect_interval * 2, 300)


@callback
def async_discover_bookoo_devices(
    hass: HomeAssistant,
    callback: Callable[[BLEDevice, AdvertisementData], None]
) -> Callable[[], None]:
    """Discover Bookoo devices using HA's bluetooth integration."""
    
    def _matcher(device: BLEDevice, adv: AdvertisementData) -> None:
        """Match Bookoo devices."""
        if device.name and device.name.startswith(DEVICE_NAME_PREFIX):
            callback(device, adv)
        elif SERVICE_UUID.lower() in [uuid.lower() for uuid in adv.service_uuids]:
            callback(device, adv)
    
    return bluetooth.async_register_callback(
        hass,
        _matcher,
        {"service_uuids": [SERVICE_UUID.lower()]},
        bluetooth.BluetoothScanningMode.ACTIVE,
    )