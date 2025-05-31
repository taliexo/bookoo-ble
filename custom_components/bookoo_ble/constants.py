"""Constants for the Bookoo BLE integration."""
from typing import Final

# Domain
DOMAIN: Final = "bookoo_ble"

# Device identifiers
DEVICE_NAME_PREFIX: Final = "BOOKOO_SC"
MANUFACTURER: Final = "Bookoo Coffee"

# BLE Service and Characteristic UUIDs
SERVICE_UUID: Final = "00000FFE-0000-1000-8000-00805F9B34FB"
CHAR_COMMAND_UUID: Final = "0000FF12-0000-1000-8000-00805F9B34FB"  # Command & Weight data notifications
CHAR_WEIGHT_UUID: Final = "0000FF11-0000-1000-8000-00805F9B34FB"   # Alternative weight data (not commonly used)
CHAR_NOTIFY_DESCRIPTOR: Final = "00002902-0000-1000-8000-00805F9B34FB"

# Nordic DFU Service (for firmware updates, not used in normal operation)
DFU_SERVICE_UUID: Final = "0000FE59-0000-1000-8000-00805F9B34FB"
DFU_CHAR_UUID: Final = "8EC90003-F315-4F60-9FB8-838830DAEA50"

# Message types (first byte of notification)
MSG_TYPE_COMMAND: Final = 0x0A
MSG_TYPE_WEIGHT: Final = 0x0B
MSG_TYPE_STATUS: Final = 0x03  # Seen in captures

# Commands
CMD_TARE: Final = bytes([0x03, 0x0A, 0x01, 0x00, 0x00, 0x08])
CMD_START_TIMER: Final = bytes([0x03, 0x0A, 0x04, 0x00, 0x00, 0x0A])
CMD_STOP_TIMER: Final = bytes([0x03, 0x0A, 0x05, 0x00, 0x00, 0x0D])
CMD_RESET_TIMER: Final = bytes([0x03, 0x0A, 0x06, 0x00, 0x00, 0x0C])
CMD_TARE_AND_START: Final = bytes([0x03, 0x0A, 0x07, 0x00, 0x00, 0x00])  # Recommended

# Beep level commands (0-5, 0 = off)
def cmd_set_beep(level: int) -> bytes:
    """Create command to set beep level (0-5)."""
    checksum = 0x03 ^ 0x0A ^ 0x02 ^ level ^ 0x00
    return bytes([0x03, 0x0A, 0x02, level, 0x00, checksum])

# Auto-off duration commands (1-30 minutes)
def cmd_set_auto_off(minutes: int) -> bytes:
    """Create command to set auto-off duration (1-30 minutes)."""
    checksum = 0x03 ^ 0x0A ^ 0x03 ^ minutes ^ 0x00
    return bytes([0x03, 0x0A, 0x03, minutes, 0x00, checksum])

# Flow smoothing command (0 = off, 1 = on)
def cmd_set_flow_smoothing(enabled: bool) -> bytes:
    """Create command to enable/disable flow smoothing."""
    value = 0x01 if enabled else 0x00
    checksum = 0x03 ^ 0x0A ^ 0x08 ^ value ^ 0x00
    return bytes([0x03, 0x0A, 0x08, value, 0x00, checksum])

# Sensor attributes
ATTR_WEIGHT: Final = "weight"
ATTR_FLOW_RATE: Final = "flow_rate"
ATTR_TIMER: Final = "timer"
ATTR_BATTERY_LEVEL: Final = "battery_level"
ATTR_STABLE: Final = "stable"
ATTR_TARE_ACTIVE: Final = "tare_active"
ATTR_FLOW_SMOOTHING: Final = "flow_smoothing"
ATTR_BEEP_LEVEL: Final = "beep_level"
ATTR_AUTO_OFF_MINUTES: Final = "auto_off_minutes"

# Sensor units
UNIT_GRAMS: Final = "g"
UNIT_GRAMS_PER_SECOND: Final = "g/s"
UNIT_MILLISECONDS: Final = "ms"
UNIT_PERCENT: Final = "%"
UNIT_MINUTES: Final = "min"

# Update intervals
SCAN_INTERVAL_SECONDS: Final = 10
NOTIFICATION_TIMEOUT_SECONDS: Final = 30
RECONNECT_INTERVAL_SECONDS: Final = 10

# Configuration defaults
DEFAULT_NAME: Final = "Bookoo Scale"
DEFAULT_BEEP_LEVEL: Final = 3
DEFAULT_AUTO_OFF_MINUTES: Final = 5
DEFAULT_FLOW_SMOOTHING: Final = False