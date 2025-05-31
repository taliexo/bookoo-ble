"""Config flow for Bookoo BLE integration."""
import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector
from bleak import BleakScanner
from bleak.backends.device import BLEDevice

from .const import (
    DOMAIN,
    DEVICE_NAME_PREFIX,
    SERVICE_UUID,
    DEFAULT_NAME,
    DEFAULT_BEEP_LEVEL,
    DEFAULT_AUTO_OFF_MINUTES,
    DEFAULT_FLOW_SMOOTHING,
)

_LOGGER = logging.getLogger(__name__)


class BookooConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bookoo BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_devices: Dict[str, BLEDevice] = {}
        self._discovered_device: Optional[BLEDevice] = None

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            if user_input.get("manual_entry"):
                return await self.async_step_manual()
            
            # Scan for devices
            return await self.async_step_scan()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional("manual_entry", default=False): bool,
            }),
            description_placeholders={
                "device_name": DEVICE_NAME_PREFIX,
            },
        )

    async def async_step_scan(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device scanning."""
        errors = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            device = self._discovered_devices.get(address)
            
            if device:
                self._discovered_device = device
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                
                return await self.async_step_configure()

        # Scan for devices
        try:
            devices = await self._async_discover_devices()
            
            if not devices:
                return self.async_show_form(
                    step_id="scan",
                    errors={"base": "no_devices_found"},
                    description_placeholders={
                        "device_name": DEVICE_NAME_PREFIX,
                    },
                )
            
            self._discovered_devices = {device.address: device for device in devices}
            
            # Create options for selector
            options = []
            for device in devices:
                name = device.name or "Unknown"
                options.append({
                    "value": device.address,
                    "label": f"{name} ({device.address})",
                })
            
            return self.async_show_form(
                step_id="scan",
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS): selector({
                        "select": {
                            "options": options,
                        }
                    }),
                }),
                errors=errors,
            )
            
        except Exception as ex:
            _LOGGER.error("Error scanning for devices: %s", ex)
            return self.async_show_form(
                step_id="scan",
                errors={"base": "scan_error"},
            )

    async def async_step_manual(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual device entry."""
        errors = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()
            
            # Validate address format
            if not self._is_valid_mac_address(address):
                errors[CONF_ADDRESS] = "invalid_address"
            else:
                await self.async_set_unique_id(address)
                self._abort_if_unique_id_configured()
                
                # Try to find device
                device = bluetooth.async_ble_device_from_address(
                    self.hass, address, connectable=True
                )
                
                if device:
                    self._discovered_device = device
                else:
                    # Create a minimal device object
                    self._discovered_device = BLEDevice(
                        address=address,
                        name=user_input.get(CONF_NAME, DEFAULT_NAME),
                        details={},
                        rssi=-80,
                    )
                
                return await self.async_step_configure()

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_configure(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle device configuration."""
        errors = {}

        if user_input is not None:
            # Create the config entry
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_ADDRESS: self._discovered_device.address,
                    CONF_NAME: user_input[CONF_NAME],
                    "beep_level": user_input.get("beep_level", DEFAULT_BEEP_LEVEL),
                    "auto_off_minutes": user_input.get("auto_off_minutes", DEFAULT_AUTO_OFF_MINUTES),
                    "flow_smoothing": user_input.get("flow_smoothing", DEFAULT_FLOW_SMOOTHING),
                },
            )

        # Default name from device or use default
        default_name = DEFAULT_NAME
        if self._discovered_device and self._discovered_device.name:
            default_name = self._discovered_device.name

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default=default_name): str,
                vol.Optional("beep_level", default=DEFAULT_BEEP_LEVEL): selector({
                    "number": {
                        "min": 0,
                        "max": 5,
                        "mode": "slider",
                    }
                }),
                vol.Optional("auto_off_minutes", default=DEFAULT_AUTO_OFF_MINUTES): selector({
                    "number": {
                        "min": 1,
                        "max": 30,
                        "unit_of_measurement": "minutes",
                    }
                }),
                vol.Optional("flow_smoothing", default=DEFAULT_FLOW_SMOOTHING): bool,
            }),
            errors=errors,
            description_placeholders={
                "device": self._discovered_device.name or self._discovered_device.address,
            },
        )

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        
        self._discovered_device = discovery_info.device
        
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm bluetooth discovery."""
        if user_input is not None:
            return await self.async_step_configure()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": self._discovered_device.name,
                "address": self._discovered_device.address,
            },
        )

    async def _async_discover_devices(self) -> list[BLEDevice]:
        """Discover Bookoo devices."""
        devices = []
        
        # Try HA's bluetooth integration first
        try:
            for device in bluetooth.async_discovered_devices(self.hass):
                if device.name and device.name.startswith(DEVICE_NAME_PREFIX):
                    devices.append(device)
                elif device.advertisement_data:
                    service_uuids = [uuid.lower() for uuid in device.advertisement_data.service_uuids]
                    if SERVICE_UUID.lower() in service_uuids:
                        devices.append(device)
        except Exception as ex:
            _LOGGER.debug("Error using HA bluetooth: %s", ex)
        
        # If no devices found, try Bleak scanner
        if not devices:
            try:
                discovered = await BleakScanner.discover(timeout=10)
                for device in discovered:
                    if device.name and device.name.startswith(DEVICE_NAME_PREFIX):
                        devices.append(device)
            except Exception as ex:
                _LOGGER.error("Error scanning with Bleak: %s", ex)
        
        return devices

    def _is_valid_mac_address(self, address: str) -> bool:
        """Check if MAC address is valid."""
        parts = address.split(":")
        if len(parts) != 6:
            return False
        
        for part in parts:
            if len(part) != 2:
                return False
            try:
                int(part, 16)
            except ValueError:
                return False
        
        return True