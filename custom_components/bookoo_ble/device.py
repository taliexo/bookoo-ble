import logging
from typing import Any, Dict, Optional, Callable

from .ble_manager import BookooBLEManager
from .constants import (
    CMD_TARE,
    CMD_START_TIMER,
    CMD_STOP_TIMER,
    CMD_RESET_TIMER,
    CMD_TARE_AND_START,
    cmd_set_beep,
    cmd_set_auto_off,
    cmd_set_flow_smoothing,
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
from .helpers import validate_checksum, format_timer # generate_checksum_byte is used by constants

_LOGGER = logging.getLogger(__name__)


class BookooDevice:
    """Represents a Bookoo BLE device, handling commands and data parsing."""

    def __init__(self, ble_manager: BookooBLEManager, name: str):
        """Initialize the Bookoo device."""
        self.ble_manager = ble_manager
        self.name = name
        self._notification_callback: Optional[Callable[[Dict[str, Any]], None]] = None

        # Device state attributes that can be updated from notifications/settings
        self.weight_g: float = 0.0
        self.flow_rate_g_s: float = 0.0
        self.timer_ms: int = 0
        self.battery_percent: int = 0
        self.is_stable: bool = False # Placeholder, needs actual logic if available
        self.beep_level: int = 0 # Can be updated from notifications or options flow
        self.auto_off_minutes: int = 0 # Can be updated
        self.flow_smoothing_enabled: bool = False # Can be updated
        self.timer_status: str = "stopped"

        self.ble_manager.set_notification_callback(self._internal_notification_handler)

    def _internal_notification_handler(self, data: bytes) -> None:
        """Internal handler to parse data and then call the registered callback."""
        parsed_data = self._parse_notification(data)
        if parsed_data and self._notification_callback:
            # Update internal state based on parsed data
            if parsed_data.get("message_type") == "weight":
                self.weight_g = parsed_data.get(ATTR_WEIGHT, self.weight_g)
                self.flow_rate_g_s = parsed_data.get(ATTR_FLOW_RATE, self.flow_rate_g_s)
                self.timer_ms = parsed_data.get("raw_timer_ms", self.timer_ms) # Use raw for state
                self.battery_percent = parsed_data.get(ATTR_BATTERY_LEVEL, self.battery_percent)
                self.is_stable = parsed_data.get(ATTR_STABLE, self.is_stable)
                self.beep_level = parsed_data.get(ATTR_BEEP_LEVEL, self.beep_level)
                self.auto_off_minutes = parsed_data.get(ATTR_AUTO_OFF_MINUTES, self.auto_off_minutes)
                self.flow_smoothing_enabled = parsed_data.get(ATTR_FLOW_SMOOTHING, self.flow_smoothing_enabled)
            elif parsed_data.get("message_type") == "status":
                self.timer_status = parsed_data.get("timer_status", self.timer_status)
            
            self._notification_callback(parsed_data)

    def set_external_notification_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Set the callback for parsed notifications to be sent to coordinator."""
        self._notification_callback = callback

    # --- Command Methods ---
    async def async_tare(self) -> bool:
        """Send tare command."""
        return await self.ble_manager.async_write_command(CMD_TARE)

    async def async_start_timer(self) -> bool:
        """Send start timer command."""
        return await self.ble_manager.async_write_command(CMD_START_TIMER)

    async def async_stop_timer(self) -> bool:
        """Send stop timer command."""
        return await self.ble_manager.async_write_command(CMD_STOP_TIMER)

    async def async_reset_timer(self) -> bool:
        """Send reset timer command."""
        return await self.ble_manager.async_write_command(CMD_RESET_TIMER)

    async def async_tare_and_start_timer(self) -> bool:
        """Send tare and start timer command."""
        return await self.ble_manager.async_write_command(CMD_TARE_AND_START)

    async def async_set_beep_level(self, level: int) -> bool:
        """Send set beep level command."""
        # Potentially update self.beep_level optimistically or upon confirmation
        return await self.ble_manager.async_write_command(cmd_set_beep(level))

    async def async_set_auto_off_minutes(self, minutes: int) -> bool:
        """Send set auto-off timer command."""
        return await self.ble_manager.async_write_command(cmd_set_auto_off(minutes))

    async def async_set_flow_smoothing(self, enabled: bool) -> bool:
        """Send set flow smoothing command."""
        return await self.ble_manager.async_write_command(cmd_set_flow_smoothing(enabled))

    # --- Parsing Logic (moved from helpers.py) ---
    def _parse_weight_notification(self, data: bytes) -> Optional[Dict[str, Any]]:
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
        
        # Validate product number and type for the 21-byte message
        if data[0] != 0x03 or data[1] != MSG_TYPE_WEIGHT: # MSG_TYPE_WEIGHT should be 0x0B
            _LOGGER.debug("Invalid weight notification header: %02x %02x", data[0], data[1])
            return None
        
        if not validate_checksum(data[:21]): # Pass the 20 data bytes + 1 checksum byte
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
        
        # TODO: Determine 'stable' from status flags if available in this message or another
        # For now, we'll assume it's not part of this specific 0x0B message directly
        # or needs to be inferred from weight changes over time.
        is_stable = False # Placeholder, update if logic is found

        return {
            ATTR_WEIGHT: weight_g,
            ATTR_FLOW_RATE: flow_rate_g_s,
            ATTR_TIMER: format_timer(timer_ms), # Formatted for sensor
            "raw_timer_ms": timer_ms, # Raw for internal state/logic
            ATTR_BATTERY_LEVEL: battery_percent,
            ATTR_STABLE: is_stable, 
            ATTR_BEEP_LEVEL: buzzer_gear,
            ATTR_AUTO_OFF_MINUTES: standby_minutes,
            ATTR_FLOW_SMOOTHING: flow_smoothing,
            "message_type": "weight",
        }

    def _parse_status_notification(self, data: bytes, expected_identifier_byte: int) -> Optional[Dict[str, Any]]:
        """
        Parse status notification data (e.g., type 0x03, length 0x0D from captures).
        Format from captures (20 data bytes + 1 checksum byte):
        - Byte 0: Product number (0x03)
        - Byte 1: Type/Length (e.g., 0x0D for status, or a specific type like 0x03 for MSG_TYPE_STATUS)
        - Byte 2: Status (0x01 = timer started, 0x00 = timer stopped)
        - Bytes 3-19: Padding (all 0x00)
        - Byte 20: Checksum
        """
        # This parser is based on the observed 21-byte messages from captures.
        # If MSG_TYPE_STATUS is 0x03, and it's byte 1, then data[1] should be 0x03.
        # If the 'type' is actually the length field (0x0D) as seen in helpers.py, adjust accordingly.
        # Let's assume for now constants.py defines MSG_TYPE_STATUS = 0x03 (or similar unique type)
        # and this type is at data[1]. If it's a fixed length message, data[1] might be length.

        if len(data) < 21: # Assuming status messages are also 21 bytes based on previous logs
            _LOGGER.debug("Status notification too short: %d bytes, data: %s", len(data), data.hex())
            return None

        # Example: if MSG_TYPE_STATUS is 0x03 and it's at data[1]
        # if data[0] != 0x03 or data[1] != MSG_TYPE_STATUS:
        # For now, using the structure from helpers.py where data[1] was 0x0D (length)
        # and the actual status type was implicitly handled.
        # This needs clarification based on constants.py and device behavior.
        # Let's assume a generic structure for now and refine if MSG_TYPE_STATUS is defined.
        
        # Validate product number and the expected identifier at data[1]
        if data[0] != 0x03 or data[1] != expected_identifier_byte:
             _LOGGER.debug("Invalid status notification header (expected product 03, type/len %02x at data[1]): received %02x %02x", expected_identifier_byte, data[0], data[1])
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

    def _parse_notification(self, data: bytes) -> Optional[Dict[str, Any]]:
        """Parse any notification from Bookoo scale."""
        if len(data) < 2:
            _LOGGER.debug("Notification too short: %d bytes", len(data))
            return None
        
        # Determine message type. Typically from a fixed byte, e.g., data[1].
        # MSG_TYPE_WEIGHT is 0x0B from constants.
        # MSG_TYPE_STATUS needs to be confirmed from constants or device behavior.
        # The original helpers.py used data[1] == 0x0D (length) for status.

        msg_identifier = data[1] # This is often the type or a length field that implies type

        if msg_identifier == MSG_TYPE_WEIGHT: # 0x0B
            return self._parse_weight_notification(data)
        elif data[0] == 0x03 and msg_identifier == 0x0D: # Specific timer status message (product 0x03, data[1] is length 0x0D)
            return self._parse_status_notification(data, expected_identifier_byte=0x0D)
        
        _LOGGER.debug("Unknown or unhandled message type/identifier: %02x, data: %s", msg_identifier, data.hex())
        # Optionally, try a more generic parse or log more details
        return None

