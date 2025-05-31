"""Bluetooth data parser for Bookoo BLE devices."""
import logging
from typing import Any, Dict, Final, Optional

from .const import (
    MSG_TYPE_WEIGHT,
    MSG_TYPE_TIMER_STATUS,
    ATTR_WEIGHT,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_BATTERY_LEVEL,
    ATTR_STABLE,
    ATTR_TARE_ACTIVE,
    ATTR_BEEP_LEVEL,
    ATTR_AUTO_OFF_MINUTES,
    ATTR_FLOW_SMOOTHING,
)
from .helpers import validate_checksum, format_timer

_LOGGER = logging.getLogger(__name__)

class BookooBluetoothParser:
    """Parser for Bookoo BLE device advertisements and notifications."""

    @staticmethod
    def parse_notification(data: bytes) -> Optional[Dict[str, Any]]:
        """Parse notification data from Bookoo device."""
        if len(data) < 2:
            _LOGGER.debug("Notification too short: %d bytes", len(data))
            return None
        
        msg_identifier = data[1]

        if msg_identifier == MSG_TYPE_WEIGHT:  # 0x0B
            return BookooBluetoothParser._parse_weight_notification(data)
        elif data[0] == 0x03 and msg_identifier == MSG_TYPE_TIMER_STATUS:  # 0x0D
            return BookooBluetoothParser._parse_status_notification(data)
        
        _LOGGER.debug("Unknown message type/identifier: %02x, data: %s", msg_identifier, data.hex())
        return None

    @staticmethod
    def _parse_weight_notification(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse weight notification data (type 0x0B).
        Format (20 data bytes + 1 checksum byte):
        - Byte 0: Product number (0x03)
        - Byte 1: Type (0x0B)
        - Bytes 2-4: Timer milliseconds (24-bit big-endian)
        - Byte 5: Unit of weight (not used, always grams)
        - Byte 6: Weight sign (+/-)
        - Bytes 7-9: Weight in grams * 100 (24-bit big-endian)
        - Byte 10: Flow rate sign (+/-)
        - Bytes 11-12: Flow rate * 100 (16-bit big-endian)
        - Byte 13: Battery percentage
        - Bytes 14-15: Standby time in minutes (16-bit big-endian)
        - Byte 16: Buzzer gear (0-5)
        - Byte 17: Flow rate smoothing switch (0/1)
        - Bytes 18-19: Reserved (0x00)
        - Byte 20: Checksum (data[:21] includes this byte)
        """
        if len(data) < 21:
            _LOGGER.debug("Weight notification too short: %d bytes, data: %s", len(data), data.hex())
            return None
        
        # Validate product number and type
        if data[0] != 0x03 or data[1] != MSG_TYPE_WEIGHT:
            _LOGGER.debug("Invalid weight notification header: %02x %02x", data[0], data[1])
            return None
        
        if not validate_checksum(data[:21]):
            return None
        
        timer_ms = (data[2] << 16) | (data[3] << 8) | data[4]
        weight_sign = -1 if data[6] else 1
        weight_raw = (data[7] << 16) | (data[8] << 8) | data[9]
        weight_g = weight_sign * (weight_raw / 100.0)
        
        flow_sign = -1 if data[10] else 1
        flow_raw = (data[11] << 8) | data[12]
        flow_rate_g_s = flow_sign * (flow_raw / 100.0)
        
        battery_percent = data[13]
        standby_minutes = (data[14] << 8) | data[15]
        buzzer_gear = data[16]
        flow_smoothing = bool(data[17])
        
        # TODO: Determine 'stable' from status flags if available
        is_stable = False  # Placeholder
        tare_active = False  # Placeholder

        return {
            ATTR_WEIGHT: weight_g,
            ATTR_FLOW_RATE: flow_rate_g_s,
            ATTR_TIMER: format_timer(timer_ms),
            "raw_timer_ms": timer_ms,
            ATTR_BATTERY_LEVEL: battery_percent,
            ATTR_STABLE: is_stable,
            ATTR_TARE_ACTIVE: tare_active,
            ATTR_BEEP_LEVEL: buzzer_gear,
            ATTR_AUTO_OFF_MINUTES: standby_minutes,
            ATTR_FLOW_SMOOTHING: flow_smoothing,
            "message_type": "weight",
        }

    @staticmethod
    def _parse_status_notification(data: bytes) -> Optional[Dict[str, Any]]:
        """
        Parse status notification data (timer status).
        Format (20 data bytes + 1 checksum byte):
        - Byte 0: Product number (0x03)
        - Byte 1: Type/Length (0x0D)
        - Byte 2: Status (0x01 = timer started, 0x00 = timer stopped)
        - Bytes 3-19: Padding (all 0x00)
        - Byte 20: Checksum
        """
        if len(data) < 21:
            _LOGGER.debug("Status notification too short: %d bytes, data: %s", len(data), data.hex())
            return None
        
        # Validate product number and identifier
        if data[0] != 0x03 or data[1] != MSG_TYPE_TIMER_STATUS:
            _LOGGER.debug("Invalid status notification header: %02x %02x", data[0], data[1])
            return None
        
        if not validate_checksum(data[:21]):
            return None
        
        timer_status_byte = data[2]
        timer_status_str = "started" if timer_status_byte == 0x01 else "stopped"
        
        return {
            "timer_status": timer_status_str,
            "raw_status_byte": timer_status_byte,
            "message_type": "status",
        }
