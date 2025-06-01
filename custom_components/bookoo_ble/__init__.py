"""The Bookoo BLE integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .coordinator import BookooDeviceCoordinator, BookooPassiveBluetoothDataProcessor
from .models import BookooBluetoothDeviceData, BookooData
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bookoo BLE component."""
    hass.data.setdefault(DOMAIN, {})
    
    # Set up services
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bookoo BLE from a config entry."""
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    _LOGGER.debug("Setting up Bookoo BLE for %s (%s)", name, address)

    # Create initial device data
    device_data = BookooBluetoothDeviceData(
        address=address,
        device_name=name,
        model="Bookoo Mini Scale",
        service_info=None,  # Will be set when we receive notifications
        data=BookooData(),
        manufacturer=MANUFACTURER,
    )
    
    # Create the passive update processor and coordinator
    passive_processor = BookooPassiveBluetoothDataProcessor(
        sensor_update_callback=lambda data_update: None,  # Placeholder, set by coordinator
    )
    
    passive_coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        processor=passive_processor,
    )
    
    # Create the device coordinator
    device_coordinator = BookooDeviceCoordinator(
        hass, device_data, passive_coordinator
    )
    
    # Connect to the device
    if not await device_coordinator.connect_and_setup():
        _LOGGER.warning("Could not connect to Bookoo device %s (%s)", name, address)
    
    # Store coordinators in hass.data
    hass.data[DOMAIN][entry.entry_id] = {
        "device_coordinator": device_coordinator,
        "passive_coordinator": passive_coordinator,
    }
    
    # Register the device in the device registry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        manufacturer=MANUFACTURER,
        name=name,
        model="Bookoo Mini Scale",
    )
    
    # Apply settings from options or config data
    current_config = {**entry.data, **entry.options}
    beep_level = current_config.get("beep_level")
    auto_off_minutes = current_config.get("auto_off_minutes")
    flow_smoothing = current_config.get("flow_smoothing")

    if beep_level is not None:
        _LOGGER.debug("Applying initial beep level: %s", beep_level)
        await device_coordinator.async_set_beep_level(beep_level)
    if auto_off_minutes is not None:
        _LOGGER.debug("Applying initial auto-off minutes: %s", auto_off_minutes)
        await device_coordinator.async_set_auto_off_minutes(auto_off_minutes)
    if flow_smoothing is not None:
        _LOGGER.debug("Applying initial flow smoothing: %s", flow_smoothing)
        await device_coordinator.async_set_flow_smoothing(flow_smoothing)
    
    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok and entry.entry_id in hass.data[DOMAIN]:
        coordinators = hass.data[DOMAIN].pop(entry.entry_id)
        device_coordinator = coordinators["device_coordinator"]
        
        # Disconnect the device coordinator
        await device_coordinator.disconnect()
        
        # If this is the last entry, unload services
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
