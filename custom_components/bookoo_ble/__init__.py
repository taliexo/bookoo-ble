"""The Bookoo BLE integration."""
from __future__ import annotations

import logging
from typing import Final

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN, MANUFACTURER
from .coordinator import BookooDeviceCoordinator, BookooPassiveBluetoothDataProcessor
from .models import BookooBluetoothDeviceData, BookooData
from .services import async_setup_services, async_unload_services

# List of platforms to set up
PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
]

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Bookoo BLE component."""
    hass.data.setdefault(DOMAIN, {})
    
    # Set up services
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bookoo BLE from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Get device info from config entry
    address = entry.data[CONF_ADDRESS]
    name = entry.data[CONF_NAME]
    
    # Create device data and processor
    processor = BookooPassiveBluetoothDataProcessor(
        sensor_update_callback=lambda update: None  # Will be set by PassiveBluetoothProcessorCoordinator
    )
    
    # Create passive coordinator
    passive_coordinator = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=bluetooth.BluetoothScanningMode.ACTIVE,
        update_method=processor,
    )
    
    # Create device coordinator
    device_coordinator = BookooDeviceCoordinator(
        hass=hass,
        device=BookooBluetoothDeviceData(
            address=address,
            device_name=name,
            model="Bookoo Scale",
            service_info=None,
            data=BookooData(),
        ),
        passive_coordinator=passive_coordinator,
    )
    
    # Store coordinators
    hass.data[DOMAIN][entry.entry_id] = {
        "device_coordinator": device_coordinator,
        "passive_coordinator": passive_coordinator,
    }

    # Set up services if not already set up
    if len(hass.data[DOMAIN]) == 1:  # Only set up services once
        await async_setup_services(hass)
    
    # Register the device in the device registry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        manufacturer=MANUFACTURER,
        name=name,
        model="Bookoo Mini Scale",
    )
    
    # Set up platforms
    current_config = {**entry.data, **entry.options}
    beep_level = current_config.get("beep_level")
    auto_off_minutes = current_config.get("auto_off_minutes")
    flow_smoothing = current_config.get("flow_smoothing")

    # Apply initial configuration settings
    # We attempt to apply these settings but don't fail the entire setup if the device
    # is temporarily unavailable. The settings can be applied later when the device connects.
    if beep_level is not None:
        _LOGGER.debug("Attempting to apply initial beep level: %s", beep_level)
        try:
            await device_coordinator.async_set_beep_level(int(beep_level))
        except Exception as e:
            _LOGGER.warning(
                "Failed to apply initial beep level to %s: %s. Will retry on next connection.",
                address, e
            )
    
    if auto_off_minutes is not None:
        _LOGGER.debug("Attempting to apply initial auto-off minutes: %s", auto_off_minutes)
        try:
            await device_coordinator.async_set_auto_off_minutes(int(auto_off_minutes))
        except Exception as e:
            _LOGGER.warning(
                "Failed to apply initial auto-off minutes to %s: %s. Will retry on next connection.",
                address, e
            )
    
    if flow_smoothing is not None:
        _LOGGER.debug("Attempting to apply initial flow smoothing: %s", flow_smoothing)
        try:
            await device_coordinator.async_set_flow_smoothing(bool(flow_smoothing))
        except Exception as e:
            _LOGGER.warning(
                "Failed to apply initial flow smoothing to %s: %s. Will retry on next connection.",
                address, e
            )
    
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
        coordinators = hass.data[DOMAIN][entry.entry_id]
        device_coordinator = coordinators["device_coordinator"]
        passive_coordinator = coordinators["passive_coordinator"]
        
        # Stop the passive coordinator to ensure proper cleanup
        # This will unregister the Bluetooth processor and stop processing updates
        if hasattr(passive_coordinator, 'async_stop'):
            try:
                await passive_coordinator.async_stop()
                _LOGGER.debug("Successfully stopped passive coordinator for %s", entry.data[CONF_ADDRESS])
            except Exception as e:
                _LOGGER.error("Error stopping passive coordinator: %s", e)
        
        # Disconnect the device coordinator
        await device_coordinator.disconnect()
        
        # Remove entry data
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Unload services if this was the last entry
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)