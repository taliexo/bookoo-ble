"""Tests for Bookoo BLE helper functions."""
import pytest
from custom_components.bookoo_ble.helpers import (
    generate_checksum_byte, # Corrected import
    validate_checksum,
    format_weight,
    format_flow_rate,
    format_timer,
)


class TestChecksum:
    """Test checksum calculation and validation."""

    def test_generate_checksum_byte(self): # Renamed test method for clarity
        """Test checksum calculation."""
        # Test data from scale_protocols.md
        data = bytes([0x03, 0x0A, 0x01, 0x00, 0x00])
        checksum = generate_checksum_byte(data) # Use correct function
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
        data = bytes([0x03]) # Only 1 byte, checksum validation needs at least 2
        assert validate_checksum(data) is False

class TestFormatters:
    """Test formatting functions."""

    def test_format_weight(self):
        """Test weight formatting."""
        assert format_weight(123.4) == "123.4"
        assert format_weight(1234.56) == "1234.6" # .1f rounds
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