"""Helper functions for parsing Bookoo BLE data."""
import logging
from typing import Dict, Optional, Any

_LOGGER = logging.getLogger(__name__)


def calculate_checksum(data: bytes) -> int:
    """Calculate XOR checksum for Bookoo protocol."""
    if len(data) < 2:
        return 0
    
    # XOR all bytes except the last one (which is the checksum)
    checksum = 0
    for byte in data[:-1]:
        checksum ^= byte
    
    return checksum


def validate_checksum(data: bytes) -> bool:
    """Validate checksum of received data."""
    if len(data) < 2:
        return False
    
    calculated = calculate_checksum(data)
    received = data[-1]
    
    if calculated != received:
        _LOGGER.debug(
            "Checksum mismatch: calculated=%02x, received=%02x", 
            calculated, 
            received
        )
        return False
    
    return True


def parse_weight_notification(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse weight notification data (type 0x0B).
    
    Format (20 bytes):
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
    - Byte 20: Checksum
    """
    if len(data) < 21:
        _LOGGER.debug("Weight notification too short: %d bytes", len(data))
        return None
    
    if data[0] != 0x03 or data[1] != 0x0B:
        _LOGGER.debug("Invalid weight notification header: %02x %02x", data[0], data[1])
        return None
    
    if not validate_checksum(data[:21]):
        return None
    
    # Parse timer (milliseconds)
    timer_ms = (data[2] << 16) | (data[3] << 8) | data[4]
    
    # Parse weight
    weight_sign = -1 if data[6] else 1
    weight_raw = (data[7] << 16) | (data[8] << 8) | data[9]
    weight_g = weight_sign * (weight_raw / 100.0)
    
    # Parse flow rate
    flow_sign = -1 if data[10] else 1
    flow_raw = (data[11] << 8) | data[12]
    flow_rate = flow_sign * (flow_raw / 100.0)
    
    # Parse other fields
    battery_percent = data[13]
    standby_minutes = (data[14] << 8) | data[15]
    buzzer_gear = data[16]
    flow_smoothing = bool(data[17])
    
    return {
        "timer_ms": timer_ms,
        "weight_g": weight_g,
        "flow_rate_g_s": flow_rate,
        "battery_percent": battery_percent,
        "standby_minutes": standby_minutes,
        "buzzer_gear": buzzer_gear,
        "flow_smoothing": flow_smoothing,
        "stable": True,  # TODO: Determine from status flags
    }


def parse_status_notification(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse status notification data (type 0x03, seen in captures).
    
    This appears to be a simplified notification with timer status.
    Format from captures:
    - Byte 0: Product number (0x03)
    - Byte 1: Length (0x0D = 13)
    - Byte 2: Status (0x01 = timer started, 0x00 = timer stopped)
    - Bytes 3-19: Padding (all 0x00)
    - Byte 20: Checksum
    """
    if len(data) < 21:
        _LOGGER.debug("Status notification too short: %d bytes", len(data))
        return None
    
    if data[0] != 0x03 or data[1] != 0x0D:
        _LOGGER.debug("Invalid status notification header: %02x %02x", data[0], data[1])
        return None
    
    if not validate_checksum(data[:21]):
        return None
    
    timer_status = "started" if data[2] == 0x01 else "stopped"
    
    return {
        "timer_status": timer_status,
        "raw_status": data[2],
    }


def parse_notification(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse any notification from Bookoo scale.
    
    Returns dict with parsed data or None if parsing failed.
    """
    if len(data) < 2:
        _LOGGER.debug("Notification too short: %d bytes", len(data))
        return None
    
    msg_type = data[1] if len(data) > 1 else None
    
    # Try to parse based on message type
    if msg_type == 0x0B:
        # Weight data
        result = parse_weight_notification(data)
        if result:
            result["message_type"] = "weight"
        return result
    elif msg_type == 0x0D:
        # Status/timer notification (seen in captures)
        result = parse_status_notification(data)
        if result:
            result["message_type"] = "status"
        return result
    else:
        # Unknown message type, try both parsers
        _LOGGER.debug("Unknown message type: %02x", msg_type if msg_type else 0)
        
        # Try weight parser first
        result = parse_weight_notification(data)
        if result:
            result["message_type"] = "weight"
            return result
        
        # Try status parser
        result = parse_status_notification(data)
        if result:
            result["message_type"] = "status"
            return result
        
        # Log unknown data for debugging
        _LOGGER.debug("Unable to parse notification: %s", data.hex())
        return None


def format_weight(weight_g: float) -> str:
    """Format weight in grams for display."""
    return f"{weight_g:.1f}"


def format_flow_rate(flow_rate_g_s: float) -> str:
    """Format flow rate in g/s for display."""
    return f"{flow_rate_g_s:.1f}"


def format_timer(timer_ms: int) -> str:
    """Format timer in MM:SS format."""
    total_seconds = timer_ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"