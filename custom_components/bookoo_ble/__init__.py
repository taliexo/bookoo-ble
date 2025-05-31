"""The Bookoo BLE integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME # Already correct, but ensuring it's from here
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .ble_manager import BookooBLEManager
from .device import BookooDevice
from .sensor import BookooDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


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
    
    # Create BLE manager
    ble_manager = BookooBLEManager(hass, address)
    
    # Create BookooDevice instance
    bookoo_device = BookooDevice(ble_manager, name)

    # Create coordinator, passing the BookooDevice instance
    coordinator = BookooDataUpdateCoordinator(hass, bookoo_device, entry)
    coordinator.bookoo_device = bookoo_device # Store device on coordinator for services
    
    # Start BLE connection (managed by ble_manager, started by BookooDevice if needed or implicitly by coordinator)
    if not await ble_manager.async_start(): # ble_manager is still started here
        raise ConfigEntryNotReady(f"Unable to connect to Bookoo device {address}")
    
    # Fetch initial data - coordinator will use bookoo_device which gets notifications
    await coordinator.async_config_entry_first_refresh()

    # Apply settings, prioritizing options, then data
    # Defaults from constants.py are used in config_flow if not set by user initially
    current_config = {**entry.data, **entry.options}

    beep_level = current_config.get("beep_level")
    auto_off_minutes = current_config.get("auto_off_minutes")
    flow_smoothing = current_config.get("flow_smoothing")

    if beep_level is not None:
        _LOGGER.debug("Applying initial beep level: %s", beep_level)
        await bookoo_device.async_set_beep_level(beep_level)
    if auto_off_minutes is not None:
        _LOGGER.debug("Applying initial auto-off minutes: %s", auto_off_minutes)
        await bookoo_device.async_set_auto_off_minutes(auto_off_minutes)
    if flow_smoothing is not None:
        _LOGGER.debug("Applying initial flow smoothing: %s", flow_smoothing)
        await bookoo_device.async_set_flow_smoothing(flow_smoothing)
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Register device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, address)},
        manufacturer=MANUFACTURER,
        name=name,
        model="Bookoo Scale",
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
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # Stop BLE manager (accessed via coordinator's bookoo_device or directly if preferred)
        await coordinator.bookoo_device.ble_manager.async_stop()
        
        # If this is the last entry, unload services
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)