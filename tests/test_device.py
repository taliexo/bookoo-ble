"""Tests for Bookoo BLE device logic."""
from unittest.mock import MagicMock
import pytest

from custom_components.bookoo_ble.device import BookooDevice
from custom_components.bookoo_ble.ble_manager import BookooBLEManager
from custom_components.bookoo_ble.helpers import generate_checksum_byte, validate_checksum # For test data setup
from custom_components.bookoo_ble.const import (
    MSG_TYPE_WEIGHT,
    ATTR_WEIGHT,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_BATTERY_LEVEL,
    ATTR_STABLE,
    ATTR_BEEP_LEVEL,
    ATTR_AUTO_OFF_MINUTES,
    ATTR_FLOW_SMOOTHING,
)

# Helper to create a BookooDevice instance with a mock BLEManager
@pytest.fixture
def bookoo_device_mock() -> BookooDevice:
    mock_ble_manager = MagicMock(spec=BookooBLEManager)
    device = BookooDevice(ble_manager=mock_ble_manager, name="TestDevice")
    return device

class TestWeightNotification:
    """Test weight notification parsing."""

    def test_parse_weight_notification_valid(self, bookoo_device_mock: BookooDevice):
        """Test parsing valid weight notification."""
        # Weight: 1234.5g, Flow: 5.6 g/s, Battery: 85%, Timer: 123456ms
        # Standby: 5 min, Buzzer: 3, Flow Smoothing: on
        data_payload = bytes([
            0x03,  # Product number
            MSG_TYPE_WEIGHT,  # Type (weight)
            0x01, 0xE2, 0x40,  # Timer: 123456ms
            0x00,  # Unit (grams)
            0x00,  # Weight sign (positive)
            0x01, 0xE2, 0x3A,  # Weight: 1234.5g (raw 123450)
            0x00,  # Flow sign (positive)
            0x02, 0x30,  # Flow: 5.60 g/s (raw 560)
            0x55,  # Battery: 85%
            0x00, 0x05,  # Standby: 5 minutes
            0x03,  # Buzzer level: 3
            0x01,  # Flow smoothing: enabled
            0x00, 0x00,  # Reserved
        ])
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])

        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is not None
        assert result["raw_timer_ms"] == 123456
        assert result[ATTR_WEIGHT] == 1234.5
        assert result[ATTR_FLOW_RATE] == 5.6
        assert result[ATTR_BATTERY_LEVEL] == 85
        assert result[ATTR_AUTO_OFF_MINUTES] == 5
        assert result[ATTR_BEEP_LEVEL] == 3
        assert result[ATTR_FLOW_SMOOTHING] is True
        assert result["message_type"] == "weight"

    def test_parse_weight_notification_negative_weight(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification with negative weight."""
        data_payload = bytes([
            0x03, MSG_TYPE_WEIGHT,
            0x00, 0x00, 0x00,  # Timer: 0ms
            0x00,  # Unit
            0x01,  # Weight sign (negative)
            0x00, 0x04, 0xD2,  # Weight: -12.34g (raw 1234)
            0x00,  # Flow sign
            0x00, 0x00,  # Flow: 0
            0x64,  # Battery: 100%
            0x00, 0x1E,  # Standby: 30 minutes
            0x00,  # Buzzer: 0
            0x00,  # Flow smoothing: disabled
            0x00, 0x00,  # Reserved
        ])
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])

        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is not None
        assert result[ATTR_WEIGHT] == -12.34

    def test_parse_weight_notification_invalid_header(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification with invalid header (wrong product number)."""
        data_payload = bytes([0x02, MSG_TYPE_WEIGHT] + [0x00] * 18) # Wrong product number
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])
        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is None

    def test_parse_weight_notification_invalid_type(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification with invalid type."""
        data_payload = bytes([0x03, 0x0A] + [0x00] * 18) # Wrong type (0x0A instead of 0x0B)
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])
        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is None

    def test_parse_weight_notification_too_short(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification with insufficient data."""
        data = bytes([0x03, MSG_TYPE_WEIGHT, 0x00, 0x00])  # Too short (4 bytes, expect 21)
        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is None

    def test_parse_weight_notification_invalid_checksum(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification with invalid checksum."""
        data_payload = bytes([
            0x03, MSG_TYPE_WEIGHT,
            0x01, 0xE2, 0x40, 0x00, 0x00, 0x01, 0xE2, 0x3A,
            0x00, 0x02, 0x30, 0x55, 0x00, 0x05, 0x03, 0x01,
            0x00, 0x00
        ])
        # Correct checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([0xFF]) # Incorrect checksum
        result = bookoo_device_mock._parse_weight_notification(data)
        assert result is None

class TestStatusNotification:
    """Test status notification parsing for _parse_status_notification."""

    def test_parse_status_notification_timer_started(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification for timer start."""
        data = bytes.fromhex("030d01000000000000000000000000000000000f") # Valid checksum
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D)
        assert result is not None
        assert result["timer_status"] == "started"
        assert result["raw_status_byte"] == 0x01
        assert result["message_type"] == "status"

    def test_parse_status_notification_timer_stopped(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification for timer stop."""
        data = bytes.fromhex("030d00000000000000000000000000000000000e") # Valid checksum
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D)
        assert result is not None
        assert result["timer_status"] == "stopped"
        assert result["raw_status_byte"] == 0x00

    def test_parse_status_notification_invalid_checksum(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification with invalid checksum."""
        data = bytes.fromhex("030d01000000000000000000000000000000000e")  # Wrong checksum for payload 030d01...
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D)
        assert result is None

    def test_parse_status_notification_too_short(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification with too short data."""
        data = bytes.fromhex("030d01")
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D)
        assert result is None

    def test_parse_status_notification_wrong_product_id(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification with wrong product ID."""
        data = bytes.fromhex("020d01000000000000000000000000000000000f") # product 0x02
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D)
        assert result is None

    def test_parse_status_notification_wrong_identifier(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification with wrong identifier byte (data[1])."""
        # Payload: 03 0C 01 ... with correct checksum for this payload
        payload = bytes.fromhex("030C0100000000000000000000000000000000")
        checksum = generate_checksum_byte(payload)
        data = payload + bytes([checksum])
        result = bookoo_device_mock._parse_status_notification(data, expected_identifier_byte=0x0D) # Expect 0x0D
        assert result is None

class TestParseNotification:
    """Test generic notification parsing (_parse_notification)."""

    def test_parse_notification_weight(self, bookoo_device_mock: BookooDevice):
        """Test parsing weight notification through generic parser."""
        data_payload = bytes([
            0x03, MSG_TYPE_WEIGHT,
            0x01, 0xE2, 0x40, 0x00, 0x00, 0x01, 0xE2, 0x3A,
            0x00, 0x02, 0x30, 0x55, 0x00, 0x05, 0x03, 0x01,
            0x00, 0x00
        ])
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])

        result = bookoo_device_mock._parse_notification(data)
        assert result is not None
        assert result["message_type"] == "weight"

    def test_parse_notification_status(self, bookoo_device_mock: BookooDevice):
        """Test parsing status notification (0x0D type) through generic parser."""
        data = bytes.fromhex("030d01000000000000000000000000000000000f") # Timer start
        result = bookoo_device_mock._parse_notification(data)
        assert result is not None
        assert result["message_type"] == "status"

    def test_parse_notification_unknown(self, bookoo_device_mock: BookooDevice):
        """Test parsing unknown notification type."""
        # Data with product 0x03 but unknown data[1] identifier (0xFF)
        data_payload = bytes([0x03, 0xFF, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                              0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12])
        checksum = generate_checksum_byte(data_payload)
        data = data_payload + bytes([checksum])
        result = bookoo_device_mock._parse_notification(data)
        assert result is None

    def test_parse_notification_too_short_for_type_check(self, bookoo_device_mock: BookooDevice):
        """Test parsing notification too short to determine type."""
        data = bytes([0x03]) # Only 1 byte
        result = bookoo_device_mock._parse_notification(data)
        assert result is None

    def test_parse_notification_empty(self, bookoo_device_mock: BookooDevice):
        """Test parsing empty notification."""
        data = bytes([])
        result = bookoo_device_mock._parse_notification(data)
        assert result is None
