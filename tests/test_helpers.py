"""Tests for Bookoo BLE helper functions."""
import pytest
from custom_components.bookoo_ble.helpers import (
    calculate_checksum,
    validate_checksum,
    parse_weight_notification,
    parse_status_notification,
    parse_notification,
    format_weight,
    format_flow_rate,
    format_timer,
)


class TestChecksum:
    """Test checksum calculation and validation."""

    def test_calculate_checksum(self):
        """Test checksum calculation."""
        # Test data from scale_protocols.md
        data = bytes([0x03, 0x0A, 0x01, 0x00, 0x00])
        checksum = calculate_checksum(data)
        assert checksum == 0x08

    def test_validate_checksum_valid(self):
        """Test valid checksum validation."""
        data = bytes([0x03, 0x0A, 0x01, 0x00, 0x00, 0x08])
        assert validate_checksum(data) is True

    def test_validate_checksum_invalid(self):
        """Test invalid checksum validation."""
        data = bytes([0x03, 0x0A, 0x01, 0x00, 0x00, 0xFF])
        assert validate_checksum(data) is False

    def test_validate_checksum_too_short(self):
        """Test checksum validation with too short data."""
        data = bytes([0x03])
        assert validate_checksum(data) is False


class TestWeightNotification:
    """Test weight notification parsing."""

    def test_parse_weight_notification_valid(self):
        """Test parsing valid weight notification."""
        # Create a valid weight notification
        # Weight: 1234.5g, Flow: 5.6 g/s, Battery: 85%, Timer: 123456ms
        data = bytes([
            0x03,  # Product number
            0x0B,  # Type (weight)
            0x01, 0xE2, 0x40,  # Timer: 123456ms
            0x00,  # Unit (grams)
            0x00,  # Weight sign (positive)
            0x01, 0xE2, 0x41,  # Weight: 123.45 kg = 123450 * 0.01g
            0x00,  # Flow sign (positive)
            0x02, 0x30,  # Flow: 5.60 g/s = 560 * 0.01
            0x55,  # Battery: 85%
            0x00, 0x05,  # Standby: 5 minutes
            0x03,  # Buzzer level: 3
            0x01,  # Flow smoothing: enabled
            0x00, 0x00,  # Reserved
            0x00,  # Checksum (placeholder)
        ])
        # Calculate correct checksum
        checksum = calculate_checksum(data[:-1])
        data = data[:-1] + bytes([checksum])

        result = parse_weight_notification(data)
        assert result is not None
        assert result["timer_ms"] == 123456
        assert result["weight_g"] == 1234.5
        assert result["flow_rate_g_s"] == 5.6
        assert result["battery_percent"] == 85
        assert result["standby_minutes"] == 5
        assert result["buzzer_gear"] == 3
        assert result["flow_smoothing"] is True

    def test_parse_weight_notification_negative_weight(self):
        """Test parsing weight notification with negative weight."""
        data = bytes([
            0x03, 0x0B,
            0x00, 0x00, 0x00,  # Timer: 0ms
            0x00,  # Unit
            0x01,  # Weight sign (negative)
            0x00, 0x04, 0xD2,  # Weight: -12.34g
            0x00,  # Flow sign
            0x00, 0x00,  # Flow: 0
            0x64,  # Battery: 100%
            0x00, 0x1E,  # Standby: 30 minutes
            0x00,  # Buzzer: 0
            0x00,  # Flow smoothing: disabled
            0x00, 0x00,  # Reserved
            0x00,  # Checksum
        ])
        checksum = calculate_checksum(data[:-1])
        data = data[:-1] + bytes([checksum])

        result = parse_weight_notification(data)
        assert result is not None
        assert result["weight_g"] == -12.34

    def test_parse_weight_notification_invalid_header(self):
        """Test parsing weight notification with invalid header."""
        data = bytes([0x02, 0x0B] + [0x00] * 19)  # Wrong product number
        result = parse_weight_notification(data)
        assert result is None

    def test_parse_weight_notification_too_short(self):
        """Test parsing weight notification with insufficient data."""
        data = bytes([0x03, 0x0B, 0x00, 0x00])  # Too short
        result = parse_weight_notification(data)
        assert result is None


class TestStatusNotification:
    """Test status notification parsing."""

    def test_parse_status_notification_timer_started(self):
        """Test parsing status notification for timer start."""
        # Data from captured BLE log
        data = bytes.fromhex("030d01000000000000000000000000000000000f")
        result = parse_status_notification(data)
        assert result is not None
        assert result["timer_status"] == "started"
        assert result["raw_status"] == 0x01

    def test_parse_status_notification_timer_stopped(self):
        """Test parsing status notification for timer stop."""
        # Data from captured BLE log
        data = bytes.fromhex("030d00000000000000000000000000000000000e")
        result = parse_status_notification(data)
        assert result is not None
        assert result["timer_status"] == "stopped"
        assert result["raw_status"] == 0x00

    def test_parse_status_notification_invalid_checksum(self):
        """Test parsing status notification with invalid checksum."""
        data = bytes.fromhex("030d01000000000000000000000000000000000e")  # Wrong checksum
        result = parse_status_notification(data)
        assert result is None


class TestParseNotification:
    """Test generic notification parsing."""

    def test_parse_notification_weight(self):
        """Test parsing weight notification through generic parser."""
        data = bytes([0x03, 0x0B] + [0x00] * 18 + [0x00])
        checksum = calculate_checksum(data[:-1])
        data = data[:-1] + bytes([checksum])

        result = parse_notification(data)
        assert result is not None
        assert result["message_type"] == "weight"

    def test_parse_notification_status(self):
        """Test parsing status notification through generic parser."""
        data = bytes.fromhex("030d01000000000000000000000000000000000f")
        result = parse_notification(data)
        assert result is not None
        assert result["message_type"] == "status"

    def test_parse_notification_unknown(self):
        """Test parsing unknown notification type."""
        data = bytes([0x03, 0xFF] + [0x00] * 5)  # Unknown type
        result = parse_notification(data)
        assert result is None


class TestFormatters:
    """Test formatting functions."""

    def test_format_weight(self):
        """Test weight formatting."""
        assert format_weight(123.4) == "123.4"
        assert format_weight(1234.56) == "1234.6"
        assert format_weight(0) == "0.0"
        assert format_weight(-12.3) == "-12.3"

    def test_format_flow_rate(self):
        """Test flow rate formatting."""
        assert format_flow_rate(5.6) == "5.6"
        assert format_flow_rate(0) == "0.0"
        assert format_flow_rate(-2.3) == "-2.3"

    def test_format_timer(self):
        """Test timer formatting."""
        assert format_timer(0) == "00:00"
        assert format_timer(59000) == "00:59"
        assert format_timer(60000) == "01:00"
        assert format_timer(3661000) == "61:01"
        assert format_timer(7199000) == "119:59"