"""Models for Bookoo BLE integration."""
from dataclasses import dataclass
from typing import Optional

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak


@dataclass
class BookooData:
    """Data for Bookoo scale."""

    weight: Optional[float] = None
    flow_rate: Optional[float] = None
    timer: Optional[str] = None
    raw_timer_ms: Optional[int] = None
    battery_level: Optional[int] = None
    is_stable: Optional[bool] = None
    tare_active: Optional[bool] = None
    beep_level: Optional[int] = None
    auto_off_minutes: Optional[int] = None
    flow_smoothing: Optional[bool] = None
    timer_status: Optional[str] = None


@dataclass
class BookooBluetoothDeviceData:
    """Data for a Bookoo Bluetooth device."""

    address: str
    device_name: str
    model: str
    service_info: BluetoothServiceInfoBleak
    data: BookooData
    firmware_version: Optional[str] = None
    hardware_version: Optional[str] = None
    manufacturer: Optional[str] = "Bookoo Coffee"
