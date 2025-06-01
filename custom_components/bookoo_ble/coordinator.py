"""Coordinator for Bookoo BLE integration."""
import asyncio
import logging
from collections.abc import Callable
from typing import Any, Dict, Optional, Union

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic
from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_ble_device_from_address,
    # BLEAK_RECONNECT_EXCEPTIONS, # Removed due to import error
)
from homeassistant.exceptions import ConfigEntryNotReady
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
            _LOGGER.debug(
                "Received notification from %s that was not parsed into usable data: %s",
                service_info.address,
                data.hex(),
            )
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
            name=f"{DOMAIN}_{device.address}", # Use a consistent naming scheme
            # No update_interval needed as we rely on notifications and on-demand commands
        )
        self.device = device
        self.passive_coordinator = passive_coordinator
        self._client: BleakClient | None = None
        self._command_char: BleakGATTCharacteristic | None = None
        self._weight_char: BleakGATTCharacteristic | None = None
        self._notification_task: asyncio.Task | None = None
        self._disconnect_event = asyncio.Event()
        self._data_lock = asyncio.Lock() # Protects _client and char access
        self._is_connected = False
        self._expected_disconnect = False # Flag to differentiate expected vs unexpected disconnects

    @property
    def is_connected(self) -> bool:
        """Return True if the client is currently connected."""
        return self._client is not None and self._client.is_connected

    async def _async_update_data(self) -> None:
        """Fetch data from BLE device. Not used if relying on notifications primarily."""
        # This method would be used if we were polling the device.
        # For now, we rely on notifications and on-demand commands.
        # If connection is lost, this could be a place to attempt reconnection periodically.
        _LOGGER.debug("Attempting to ensure connection for %s", self.device.address)
        if not await self.connect_and_setup():
            _LOGGER.warning("Failed to ensure connection for %s", self.device.address)
        return None

    async def async_config_entry_first_refresh(self) -> None:
        """Connect to the device and setup notifications on first refresh."""
        # This is called by HA after the config entry is setup.
        # We use it to establish the initial connection.
        if not await self.connect_and_setup():
            raise ConfigEntryNotReady(f"Could not connect to {self.device.device_name}")

    async def connect_and_setup(self) -> bool:
        """Connect to the device and set up notifications."""
        async with self._data_lock:
            if self._client and self._client.is_connected:
                _LOGGER.debug("Already connected to %s", self.device.address)
                return True

            _LOGGER.debug("Attempting to connect to %s", self.device.address)
            ble_device = bluetooth.async_ble_device_from_address(self.hass, self.device.address, connectable=True)
            if not ble_device:
                _LOGGER.warning("Device %s not found by Bluetooth manager", self.device.address)
                return False

            client = BleakClient(ble_device, disconnected_callback=self._handle_disconnect)

            try:
                await client.connect(timeout=10.0)
                _LOGGER.info("Successfully connected to %s", self.device.address)
                self._client = client
                self._is_connected = True
                self._expected_disconnect = False

                # Get services and characteristics
                svcs = await client.get_services()
                self._command_char = svcs.get_characteristic(CHAR_COMMAND_UUID)
                self._weight_char = svcs.get_characteristic(CHAR_WEIGHT_UUID)

                if not self._command_char:
                    _LOGGER.error("Command characteristic %s not found on %s", CHAR_COMMAND_UUID, self.device.address)
                    await self.disconnect() # Clean disconnect
                    return False
                if not self._weight_char:
                    _LOGGER.error("Weight characteristic %s not found on %s", CHAR_WEIGHT_UUID, self.device.address)
                    await self.disconnect() # Clean disconnect
                    return False

                # Start notifications
                self._disconnect_event.clear()
                await client.start_notify(self._weight_char, self._notification_handler)
                _LOGGER.debug("Started notifications for weight char on %s", self.device.address)
                await client.start_notify(self._command_char, self._notification_handler)
                _LOGGER.debug("Started notifications for command char on %s", self.device.address)
                
                # This task was for waiting for initial notifications, can be removed or adapted
                # if self._notification_task:
                #    self._notification_task.cancel()
                # self._notification_task = asyncio.create_task(self._wait_for_notifications())
                
                self.async_update_listeners() # Notify entities about connection status change
                return True

            except (BleakError, asyncio.TimeoutError) as err:
                _LOGGER.error("Error connecting to %s: %s", self.device.address, err)
                await self.disconnect() # Ensure client is cleaned up if connect fails
                return False
            except Exception as err: # Catch any other unexpected errors during connect
                _LOGGER.error("Unexpected error connecting to %s: %s", self.device.address, err, exc_info=True)
                await self.disconnect()
                return False

    async def disconnect(self) -> None:
        """Disconnect from the device and clean up resources."""
        _LOGGER.debug("Disconnecting from %s", self.device.address)
        async with self._data_lock:
            self._expected_disconnect = True # Mark that this disconnect is intentional
            client = self._client
            self._client = None # Clear client immediately
            self._is_connected = False
            self._command_char = None
            self._weight_char = None

            if self._notification_task:
                self._notification_task.cancel()
                self._notification_task = None

            if client and client.is_connected:
                try:
                    # Stop notifications before disconnecting if characteristics are known
                    # This might fail if connection is already lost, so wrap in try-except
                    try:
                        if client.services.get_characteristic(CHAR_WEIGHT_UUID):
                             await client.stop_notify(CHAR_WEIGHT_UUID)
                        if client.services.get_characteristic(CHAR_COMMAND_UUID):
                             await client.stop_notify(CHAR_COMMAND_UUID)
                    except BleakError as e:
                        _LOGGER.debug("BleakError stopping notifications during disconnect: %s", e)
                    
                    await client.disconnect()
                    _LOGGER.info("Successfully disconnected from %s", self.device.address)
                except BleakError as err:
                    _LOGGER.error("Error during disconnect from %s: %s", self.device.address, err)
            elif client: # Client exists but not connected, ensure it's cleaned up
                 _LOGGER.debug("Client for %s was not connected, ensuring cleanup.", self.device.address)
                 try:
                     await client.disconnect() # Attempt disconnect anyway to be safe
                 except Exception:
                     pass # Ignore errors if already disconnected or uninitialized
        self.async_update_listeners() # Notify entities

    def _handle_disconnect(self, client: BleakClient) -> None:
        """Handle Bluetooth disconnection."""
        if self._expected_disconnect:
            _LOGGER.debug("Expected disconnect from %s", client.address)
            self._expected_disconnect = False # Reset flag
            return

        _LOGGER.warning("Device %s disconnected unexpectedly", client.address)
        # Do not attempt to use the 'client' object here as it's disconnected.
        # Clear our state and notify listeners.
        async def clear_state_and_notify(): # Use async def for hass.add_job
            async with self._data_lock:
                self._client = None
                self._is_connected = False
                self._command_char = None
                self._weight_char = None
            self.async_update_listeners()
            # Optionally, schedule a reconnect attempt or rely on next command/poll
            # For now, we won't auto-reconnect here to avoid connection storms.
            # Reconnection will be attempted on next service call or if _async_update_data is polled.

        # Schedule the state clearing and listener update in the HA event loop
        self.hass.async_create_task(clear_state_and_notify())

    def _notification_handler(self, _: int, data: bytearray) -> None:
        """Handle BLE notification from the device.
        
        This handles notifications from both characteristics:
        - Weight data on 0xFF11 characteristic (data[1]=0x0B)
        - Timer status on 0xFF12 characteristic (data[0]=0x03, data[1]=0x0D)
        """
        data_bytes = bytes(data)
        
        # Log the notification for debugging
        _LOGGER.debug(
            "Received notification: %s, length: %d", 
            data_bytes.hex(), 
            len(data_bytes)
        )
        
        # Update the internal state via the passive coordinator
        # This is thread-safe as it does not modify our connection state
        self.passive_coordinator.processor.update_from_notification(
            self.device.service_info, data_bytes
        )
        
        # Set flag to indicate we received data - atomic operation
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
        async with self._data_lock: # Ensure exclusive access for command sending sequence
            if not self.is_connected or not self._command_char:
                _LOGGER.debug("Not connected or command char not found, attempting to connect before sending command to %s", self.device.address)
                if not await self.connect_and_setup(): # This also acquires the lock
                    _LOGGER.error("Failed to connect, cannot send command to %s", self.device.address)
                    return False
            
            # At this point, self._client and self._command_char should be valid if connect_and_setup succeeded
            if not self._client or not self._command_char: # Double check after potential connect_and_setup
                _LOGGER.error("Client or command characteristic still not available after connection attempt for %s", self.device.address)
                return False
            
            client = self._client
            command_char = self._command_char

        # Release lock before actual I/O operation
        try:
            _LOGGER.debug("Sending command to %s: %s", self.device.address, command.hex())
            await client.write_gatt_char(command_char, command, response=True) # Request response if char supports it
            _LOGGER.debug("Successfully sent command to %s", self.device.address)
            return True
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout sending command to %s", self.device.address)
        except BleakError as err:
            _LOGGER.error("BleakError sending command to %s: %s", self.device.address, err)
            # If a BleakError occurs, the connection might be compromised.
            # Schedule a disconnect to clean up and allow re-connection on next attempt.
            self.hass.async_create_task(self.disconnect())
        except Exception as err:
            _LOGGER.error("Unexpected error sending command to %s: %s", self.device.address, err, exc_info=True)
            self.hass.async_create_task(self.disconnect())
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
