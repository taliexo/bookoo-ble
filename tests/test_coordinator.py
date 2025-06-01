"""Tests for Bookoo BLE coordinator."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant

from custom_components.bookoo_ble.coordinator import (
    BookooDeviceCoordinator,
    BookooPassiveBluetoothDataProcessor,
)
from custom_components.bookoo_ble.models import BookooBluetoothDeviceData, BookooData
from custom_components.bookoo_ble.const import (
    CHAR_COMMAND_UUID,
    CHAR_WEIGHT_UUID,
    CMD_TARE,
    MSG_TYPE_WEIGHT,
    MSG_TYPE_TIMER_STATUS,
)


@pytest.fixture
def mock_service_info():
    """Create a mock BluetoothServiceInfoBleak."""
    service_info = MagicMock(spec=BluetoothServiceInfoBleak)
    service_info.address = "AA:BB:CC:DD:EE:FF"
    service_info.name = "BOOKOO_SC"
    service_info.device.name = "BOOKOO_SC"
    return service_info


@pytest.fixture
def mock_device_data(mock_service_info):
    """Create mock device data."""
    return BookooBluetoothDeviceData(
        address="AA:BB:CC:DD:EE:FF",
        device_name="BOOKOO_SC",
        model="Bookoo Mini Scale",
        service_info=mock_service_info,
        data=BookooData(),
    )


@pytest.fixture
def mock_passive_coordinator():
    """Create mock passive coordinator."""
    coordinator = MagicMock(spec=PassiveBluetoothProcessorCoordinator)
    coordinator.processor = MagicMock(spec=BookooPassiveBluetoothDataProcessor)
    return coordinator


@pytest.fixture
def mock_bleak_client():
    """Create mock BleakClient."""
    client = MagicMock()
    client.is_connected = True
    
    # Create mock services and characteristics
    command_char = MagicMock()
    command_char.uuid = CHAR_COMMAND_UUID
    
    weight_char = MagicMock()
    weight_char.uuid = CHAR_WEIGHT_UUID
    
    service = MagicMock()
    service.uuid = "00000FFE-0000-1000-8000-00805F9B34FB"
    service.characteristics = [command_char, weight_char]
    
    client.services = [service]
    client.write_gatt_char = AsyncMock()
    client.start_notify = AsyncMock()
    client.stop_notify = AsyncMock()
    client.disconnect = AsyncMock()
    
    return client, command_char, weight_char


class TestBookooDeviceCoordinator:
    """Test BookooDeviceCoordinator."""

    @pytest.mark.asyncio
    async def test_connect_and_setup(self, mock_device_data, mock_passive_coordinator, mock_bleak_client):
        """Test connect_and_setup method."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_client, mock_command_char, mock_weight_char = mock_bleak_client
        
        coordinator = BookooDeviceCoordinator(
            mock_hass, mock_device_data, mock_passive_coordinator
        )
        
        # Mock the establish_connection function
        with patch("custom_components.bookoo_ble.coordinator.establish_connection", return_value=mock_client) as mock_connect:
            # Call connect_and_setup
            result = await coordinator.connect_and_setup()
            
            # Verify connection was established
            assert result is True
            mock_connect.assert_called_once()
            
            # Verify notifications were started
            assert mock_client.start_notify.call_count == 2
            mock_client.start_notify.assert_any_call(mock_weight_char, coordinator._notification_handler)
            mock_client.start_notify.assert_any_call(mock_command_char, coordinator._notification_handler)

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_device_data, mock_passive_coordinator, mock_bleak_client):
        """Test disconnect method."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_client, mock_command_char, mock_weight_char = mock_bleak_client
        
        coordinator = BookooDeviceCoordinator(
            mock_hass, mock_device_data, mock_passive_coordinator
        )
        coordinator._client = mock_client
        coordinator._command_char = mock_command_char
        coordinator._weight_char = mock_weight_char
        
        # Call disconnect
        await coordinator.disconnect()
        
        # Verify notifications were stopped
        assert mock_client.stop_notify.call_count == 2
        mock_client.stop_notify.assert_any_call(mock_weight_char)
        mock_client.stop_notify.assert_any_call(mock_command_char)
        
        # Verify client was disconnected
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_command(self, mock_device_data, mock_passive_coordinator, mock_bleak_client):
        """Test send_command method."""
        mock_hass = MagicMock(spec=HomeAssistant)
        mock_client, mock_command_char, mock_weight_char = mock_bleak_client
        
        coordinator = BookooDeviceCoordinator(
            mock_hass, mock_device_data, mock_passive_coordinator
        )
        coordinator._client = mock_client
        coordinator._command_char = mock_command_char
        coordinator._weight_char = mock_weight_char
        
        # Call send_command
        result = await coordinator.send_command(CMD_TARE)
        
        # Verify command was sent
        assert result is True
        mock_client.write_gatt_char.assert_called_once_with(mock_command_char, CMD_TARE)

    def test_notification_handler(self, mock_device_data, mock_passive_coordinator):
        """Test _notification_handler method."""
        mock_hass = MagicMock(spec=HomeAssistant)
        
        coordinator = BookooDeviceCoordinator(
            mock_hass, mock_device_data, mock_passive_coordinator
        )
        
        # Test weight notification
        weight_data = bytes([
            0x03, MSG_TYPE_WEIGHT,  # Product number and type
            0x00, 0x00, 0x00,  # Timer
            0x00, 0x00, 0x00, 0x00, 0x00,  # Rest of payload
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        coordinator._notification_handler(0, weight_data)
        
        # Verify processor was called with the notification
        mock_passive_coordinator.processor.update_from_notification.assert_called_once_with(
            mock_device_data.service_info, weight_data
        )
        
        # Test timer status notification
        mock_passive_coordinator.processor.update_from_notification.reset_mock()
        timer_data = bytes([
            0x03, MSG_TYPE_TIMER_STATUS,  # Product number and type 0x0D for timer status
            0x01,  # Timer started
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Rest of payload
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        coordinator._notification_handler(0, timer_data)
        
        # Verify processor was called with the timer notification
        mock_passive_coordinator.processor.update_from_notification.assert_called_once_with(
            mock_device_data.service_info, timer_data
        )


class TestBookooPassiveBluetoothDataProcessor:
    """Test BookooPassiveBluetoothDataProcessor."""

    def test_update_from_notification_weight(self, mock_service_info):
        """Test update_from_notification method with weight data."""
        callback_mock = MagicMock()
        processor = BookooPassiveBluetoothDataProcessor(callback_mock)
        
        # Create weight notification data
        weight_data = bytes([
            0x03, MSG_TYPE_WEIGHT,  # Product number and type
            0x00, 0x00, 0x00,  # Timer: 0ms
            0x00,  # Unit
            0x00,  # Weight sign (positive)
            0x00, 0x03, 0xE8,  # Weight: 10.0g (raw 1000)
            0x00,  # Flow sign
            0x00, 0x00,  # Flow: 0
            0x64,  # Battery: 100%
            0x00, 0x05,  # Standby: 5 minutes
            0x03,  # Buzzer: 3
            0x01,  # Flow smoothing: enabled
            0x00, 0x00,  # Reserved
            0x00  # Placeholder for checksum (not used in this test)
        ])
        
        # Mock the parse_notification method
        with patch("custom_components.bookoo_ble.parser.BookooBluetoothParser.parse_notification") as mock_parse:
            mock_parse.return_value = {
                "weight": 10.0,
                "flow_rate": 0.0,
                "timer": "00:00",
                "raw_timer_ms": 0,
                "battery_level": 100,
                "stable": False,
                "tare_active": False,
                "beep_level": 3,
                "auto_off_minutes": 5,
                "flow_smoothing": True,
                "message_type": "weight",
            }
            
            # Call update_from_notification
            processor.update_from_notification(mock_service_info, weight_data)
            
            # Verify parser was called
            mock_parse.assert_called_once_with(weight_data)
            
            # Verify callback was called
            assert callback_mock.call_count == 1
            
            # Verify device was created and updated
            device = processor._tracked_devices.get(mock_service_info.address)
            assert device is not None
            assert device.data.weight == 10.0
            assert device.data.flow_rate == 0.0
            assert device.data.battery_level == 100
            assert device.data.beep_level == 3
            assert device.data.auto_off_minutes == 5
            assert device.data.flow_smoothing is True

    def test_update_from_notification_timer_status(self, mock_service_info):
        """Test update_from_notification method with timer status data."""
        callback_mock = MagicMock()
        processor = BookooPassiveBluetoothDataProcessor(callback_mock)
        
        # Create timer status notification data
        timer_data = bytes([
            0x03, MSG_TYPE_TIMER_STATUS,  # Product number and type 0x0D for timer status
            0x01,  # Timer started
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  # Rest of payload
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00  # Placeholder for checksum (not used in this test)
        ])
        
        # Mock the parse_notification method
        with patch("custom_components.bookoo_ble.parser.BookooBluetoothParser.parse_notification") as mock_parse:
            mock_parse.return_value = {
                "timer_status": "started",
                "raw_status_byte": 0x01,
                "message_type": "status",
            }
            
            # Call update_from_notification
            processor.update_from_notification(mock_service_info, timer_data)
            
            # Verify parser was called
            mock_parse.assert_called_once_with(timer_data)
            
            # Verify callback was called
            assert callback_mock.call_count == 1
            
            # Verify device was created and updated
            device = processor._tracked_devices.get(mock_service_info.address)
            assert device is not None
            assert device.data.timer_status == "started"
