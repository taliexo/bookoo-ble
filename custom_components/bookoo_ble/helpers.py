"""Helper functions for parsing Bookoo BLE data."""
import logging
from typing import Dict, Optional, Any

_LOGGER = logging.getLogger(__name__)





def generate_checksum_byte(payload: bytes) -> int:
    """Calculate XOR checksum for Bookoo command payload."""
    checksum = 0
    for byte in payload:
        checksum ^= byte
    return checksum


def validate_checksum(data_with_checksum: bytes) -> bool:
    """Validate checksum of received data."""
    if len(data_with_checksum) < 2: # Need at least 1 payload byte and 1 checksum byte
        _LOGGER.debug("Data too short for checksum validation: %d bytes", len(data_with_checksum))
        return False
    
    payload = data_with_checksum[:-1]
    received_checksum = data_with_checksum[-1]
    calculated_checksum = generate_checksum_byte(payload)
    
    if calculated_checksum != received_checksum:
        _LOGGER.debug(
            "Checksum mismatch: calculated=%02x, received=%02x, payload=%s", 
            calculated_checksum, 
            received_checksum,
            payload.hex()
        )
        return False
    
    return True


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