"""Coordinator for Bookoo BLE integration."""
import asyncio
import logging
from collections.abc import Callable
from typing import Any, Dict, Optional, Union

from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic
from bleak.exc import BleakError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS, BleakClientWithServiceCache, establish_connection
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CHAR_COMMAND_UUID,
    CHAR_WEIGHT_UUID,
    CMD_RESET_TIMER,
    CMD_START_TIMER,
    CMD_STOP_TIMER,
    CMD_TARE,
    CMD_TARE_AND_START_TIMER,
    DOMAIN,
    NOTIFICATION_TIMEOUT_SECONDS,
    SERVICE_UUID,
    cmd_set_auto_off,
    cmd_set_beep,
    cmd_set_flow_smoothing,
)
from .models import BookooBluetoothDeviceData, BookooData
from .parser import BookooBluetoothParser

_LOGGER = logging.getLogger(__name__)

class BookooPassiveBluetoothDataProcessor(PassiveBluetoothDataProcessor):
    """Data processor for Bookoo BLE devices."""

    def __init__(
        self,
        sensor_update_callback: Callable[[PassiveBluetoothDataUpdate], None],
    ) -> None:
        """Initialize the data processor."""
        super().__init__(sensor_update_callback)
        self._tracked_devices: Dict[str, BookooBluetoothDeviceData] = {}

    def update_device_info(
        self, service_info: BluetoothServiceInfoBleak
    ) -> BookooBluetoothDeviceData:
        """Create or update device information."""
        address = service_info.address
        device_name = service_info.name or "Bookoo Scale"
        model = "Bookoo Mini Scale"

        if address in self._tracked_devices:
            device = self._tracked_devices[address]
            device.service_info = service_info
        else:
            device = BookooBluetoothDeviceData(
                address=address,
                device_name=device_name,
                model=model,
                service_info=service_info,
                data=BookooData(),
            )
            self._tracked_devices[address] = device

        return device

    def update_from_notification(
        self, service_info: BluetoothServiceInfoBleak, data: bytes
    ) -> None:
        """Update from notification data."""
        device = self.update_device_info(service_info)
        
        parsed_data = BookooBluetoothParser.parse_notification(data)
        if not parsed_data:
            return
            
        # Update our local data
        if parsed_data.get("message_type") == "weight":
            if "weight" in parsed_data:
                device.data.weight = parsed_data["weight"]
            if "flow_rate" in parsed_data:
                device.data.flow_rate = parsed_data["flow_rate"]
            if "timer" in parsed_data:
                device.data.timer = parsed_data["timer"]
            if "raw_timer_ms" in parsed_data:
                device.data.raw_timer_ms = parsed_data["raw_timer_ms"]
            if "battery_level" in parsed_data:
                device.data.battery_level = parsed_data["battery_level"]
            if "stable" in parsed_data:
                device.data.is_stable = parsed_data["stable"]
            if "tare_active" in parsed_data:
                device.data.tare_active = parsed_data["tare_active"]
            if "beep_level" in parsed_data:
                device.data.beep_level = parsed_data["beep_level"]
            if "auto_off_minutes" in parsed_data:
                device.data.auto_off_minutes = parsed_data["auto_off_minutes"]
            if "flow_smoothing" in parsed_data:
                device.data.flow_smoothing = parsed_data["flow_smoothing"]
        elif parsed_data.get("message_type") == "status":
            if "timer_status" in parsed_data:
                device.data.timer_status = parsed_data["timer_status"]
        
        # Create an entity map for the passive update processor
        entity_key_map = {}
        entity_data = {}
        
        # Map each attribute to a unique entity key
        for key, value in parsed_data.items():
            if key != "message_type" and key != "raw_timer_ms" and key != "raw_status_byte":
                entity_key = PassiveBluetoothEntityKey(
                    key=key,
                    device_id=service_info.address,
                )
                entity_key_map[entity_key] = device
                entity_data[entity_key] = value
                
        if entity_data:
            self.async_handle_update(
                service_info.address,
                {
                    "entity_data": entity_data,
                    "entity_descriptions": {},
                    "entity_names": {},
                    "entity_pictures": {},
                },
            )


class BookooDeviceCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for interacting with a Bookoo BLE device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: BookooBluetoothDeviceData,
        passive_coordinator: PassiveBluetoothProcessorCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{device.device_name} ({device.address})",
        )
        self.device = device
        self.passive_coordinator = passive_coordinator
        self._client: Optional[BleakClientWithServiceCache] = None
        self._command_char: Optional[BleakGATTCharacteristic] = None
        self._weight_char: Optional[BleakGATTCharacteristic] = None
        self._notification_task: Optional[asyncio.Task] = None
        self._disconnect_event = asyncio.Event()
        self._data_lock = asyncio.Lock()
        self._update_received = False

    async def _async_update_data(self) -> None:
        """No regular updates needed - we use notifications."""
        return None

    async def connect_and_setup(self) -> bool:
        """Connect to the device and set up notifications."""
        if self._client and self._client.is_connected:
            return True
            
        ble_device = self.device.service_info.device
        if not ble_device:
            _LOGGER.error("No BLEDevice available for %s", self.device.address)
            return False
            
        try:
            _LOGGER.debug("Connecting to %s", self.device.address)
            self._client = await establish_connection(
                BleakClientWithServiceCache,
                ble_device,
                self.device.address,
                disconnected_callback=self._handle_disconnect,
                timeout=10.0,
            )
            
            _LOGGER.debug("Connected to %s", self.device.address)
            
            # Get the command and weight characteristics
            for service in self._client.services:
                if service.uuid.lower() == SERVICE_UUID.lower():
                    for char in service.characteristics:
                        if char.uuid.lower() == CHAR_COMMAND_UUID.lower():
                            self._command_char = char
                        elif char.uuid.lower() == CHAR_WEIGHT_UUID.lower():
                            self._weight_char = char
            
            if not self._command_char:
                _LOGGER.error("Command characteristic not found on %s", self.device.address)
                await self._client.disconnect()
                return False
                
            if not self._weight_char:
                _LOGGER.error("Weight characteristic not found on %s", self.device.address)
                await self._client.disconnect()
                return False
                
            # Set up notification handlers
            self._disconnect_event.clear()
            
            # Start notifications for weight data
            await self._client.start_notify(
                self._weight_char, self._notification_handler
            )
            
            # Start notifications for command/status data
            await self._client.start_notify(
                self._command_char, self._notification_handler
            )
            
            # Wait for first notification or timeout
            self._notification_task = asyncio.create_task(
                self._wait_for_notifications()
            )
            
            return True
            
        except (BleakError, *BLEAK_RETRY_EXCEPTIONS) as err:
            _LOGGER.error("Error connecting to %s: %s", self.device.address, err)
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:  # pylint: disable=broad-except
                    pass
                self._client = None
            return False

    async def disconnect(self) -> None:
        """Disconnect from the device."""
        if self._notification_task:
            self._notification_task.cancel()
            self._notification_task = None
            
        if self._client and self._client.is_connected:
            try:
                if self._weight_char:
                    await self._client.stop_notify(self._weight_char)
                if self._command_char:
                    await self._client.stop_notify(self._command_char)
                await self._client.disconnect()
            except (BleakError, *BLEAK_RETRY_EXCEPTIONS) as err:
                _LOGGER.error("Error disconnecting from %s: %s", self.device.address, err)
            finally:
                self._client = None
                self._command_char = None
                self._weight_char = None

    def _handle_disconnect(self, _: BLEDevice) -> None:
        """Handle disconnection event."""
        _LOGGER.debug("Device %s disconnected", self.device.address)
        self._disconnect_event.set()
        self._client = None
        self._command_char = None
        self._weight_char = None
        # Schedule reconnection
        asyncio.create_task(self.connect_and_setup())

    def _notification_handler(self, _: int, data: bytearray) -> None:
        """Handle BLE notification from the device."""
        data_bytes = bytes(data)
        
        # Update the internal state via the passive coordinator
        self.passive_coordinator.processor.update_from_notification(
            self.device.service_info, data_bytes
        )
        
        # Set flag to indicate we received data
        self._update_received = True

    async def _wait_for_notifications(self) -> None:
        """Wait for notifications or timeout."""
        try:
            async with asyncio.timeout(NOTIFICATION_TIMEOUT_SECONDS):
                # Wait until we receive data or disconnect
                while not self._update_received and not self._disconnect_event.is_set():
                    await asyncio.sleep(1)
                
                if not self._update_received and not self._disconnect_event.is_set():
                    _LOGGER.warning(
                        "No notifications received from %s after %d seconds",
                        self.device.address,
                        NOTIFICATION_TIMEOUT_SECONDS,
                    )
                    await self.disconnect()
        except asyncio.TimeoutError:
            _LOGGER.warning(
                "Timeout waiting for notifications from %s",
                self.device.address,
            )
            await self.disconnect()
        except asyncio.CancelledError:
            pass
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error waiting for notifications: %s", err)

    async def send_command(self, command: bytes) -> bool:
        """Send a command to the device."""
        if not self._client or not self._client.is_connected or not self._command_char:
            if not await self.connect_and_setup():
                return False
                
        try:
            async with asyncio.timeout(5):  # 5 second timeout
                await self._client.write_gatt_char(self._command_char, command)
                _LOGGER.debug("Sent command: %s", command.hex())
                return True
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout sending command to %s", self.device.address)
            return False
        except (BleakError, *BLEAK_RETRY_EXCEPTIONS) as err:
            _LOGGER.error("Error sending command to %s: %s", self.device.address, err)
            return False

    # Command methods
    async def async_tare(self) -> bool:
        """Send tare command."""
        return await self.send_command(CMD_TARE)

    async def async_start_timer(self) -> bool:
        """Send start timer command."""
        return await self.send_command(CMD_START_TIMER)

    async def async_stop_timer(self) -> bool:
        """Send stop timer command."""
        return await self.send_command(CMD_STOP_TIMER)

    async def async_reset_timer(self) -> bool:
        """Send reset timer command."""
        return await self.send_command(CMD_RESET_TIMER)

    async def async_tare_and_start_timer(self) -> bool:
        """Send tare and start timer command."""
        return await self.send_command(CMD_TARE_AND_START_TIMER)

    async def async_set_beep_level(self, level: int) -> bool:
        """Send set beep level command."""
        level = max(0, min(5, level))  # Ensure level is between 0-5
        return await self.send_command(cmd_set_beep(level))

    async def async_set_auto_off_minutes(self, minutes: int) -> bool:
        """Send set auto-off timer command."""
        minutes = max(1, min(30, minutes))  # Ensure minutes is between 1-30
        return await self.send_command(cmd_set_auto_off(minutes))

    async def async_set_flow_smoothing(self, enabled: bool) -> bool:
        """Send set flow smoothing command."""
        return await self.send_command(cmd_set_flow_smoothing(enabled))
