"""Services for Bookoo BLE integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Awaitable, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import entity_registry as er, config_validation as cv
from homeassistant.helpers.entity_platform import async_get_platforms

from .const import (
    DOMAIN,
    DEFAULT_BEEP_LEVEL,
    DEFAULT_AUTO_OFF_MINUTES,
    DEFAULT_FLOW_SMOOTHING,
    ATTR_ENTITY_ID,
    ATTR_DEVICE_ID,
)
from .coordinator import BookooDeviceCoordinator

_LOGGER = logging.getLogger(__name__)

# Service schemas
SERVICE_SCHEMA_BASE = vol.Schema(
    {
        vol.Exclusive(ATTR_ENTITY_ID, "id"): cv.entity_id,
        vol.Exclusive(ATTR_DEVICE_ID, "id"): vol.All(cv.string, vol.Lower),
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_BEEP_LEVEL = SERVICE_SCHEMA_BASE.extend(
    {
        vol.Required(vol.Any(ATTR_ENTITY_ID, ATTR_DEVICE_ID)): vol.Any(cv.string, [cv.string]),
        vol.Required("level", default=DEFAULT_BEEP_LEVEL): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=5)
        ),
    }
)

SERVICE_SCHEMA_AUTO_OFF = SERVICE_SCHEMA_BASE.extend(
    {
        vol.Required(vol.Any(ATTR_ENTITY_ID, ATTR_DEVICE_ID)): vol.Any(cv.string, [cv.string]),
        vol.Required("minutes", default=DEFAULT_AUTO_OFF_MINUTES): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
    }
)

SERVICE_SCHEMA_FLOW_SMOOTHING = SERVICE_SCHEMA_BASE.extend(
    {
        vol.Required(vol.Any(ATTR_ENTITY_ID, ATTR_DEVICE_ID)): vol.Any(cv.string, [cv.string]),
        vol.Required("enabled", default=DEFAULT_FLOW_SMOOTHING): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Bookoo BLE services."""
    
    async def get_bookoo_coordinator_from_entity(entity_id: str) -> BookooDeviceCoordinator:
        """Get coordinator directly from hass.data."""
        entity_registry = er.async_get(hass)
        entity = entity_registry.async_get(entity_id)
        
        if entity and entity.config_entry_id:
            # Get coordinator from the config entry
            if entity.config_entry_id in hass.data.get(DOMAIN, {}):
                coordinators = hass.data[DOMAIN][entity.config_entry_id]
                if "device_coordinator" in coordinators:
                    return coordinators["device_coordinator"]
        
        # If not found via entity registry, try to find any available coordinator
        for entry_id, coordinators in hass.data.get(DOMAIN, {}).items():
            if "device_coordinator" in coordinators:
                device_coordinator = coordinators["device_coordinator"]
                if isinstance(device_coordinator, BookooDeviceCoordinator):
                    return device_coordinator
                
        raise ValueError(f"No coordinator found for {entity_id}")

    async def _execute_service(entity_id_or_list: str | list[str], action: Callable[..., Awaitable[bool]], *args, **kwargs):
        """Execute a service with the given action on the coordinator."""
        # Validate entity_id input
        if not entity_id_or_list:
            _LOGGER.error("No entity_id provided for service call")
            return
            
        # Process single entity ID or pick the first from a list if provided
        if isinstance(entity_id_or_list, list):
            if not entity_id_or_list:  # Check for empty list
                _LOGGER.error("Empty entity_id list provided for service call")
                return
            entity_id = entity_id_or_list[0]  # Take the first entity ID
        else:
            entity_id = entity_id_or_list
        
        try:
            async with asyncio.timeout(10):  # 10 second timeout for service execution
                coordinator = await get_bookoo_coordinator_from_entity(entity_id)
                if not coordinator.is_connected:
                    _LOGGER.warning(
                        "Service %s called for %s, but device is not connected.",
                        action.__name__,
                        coordinator.device.address # or entity_id if preferred for logging
                    )
                    # Optionally, you could return here or raise an error to prevent further action
                    # For now, we'll let it proceed, as send_command in coordinator will try to connect.
                
                if not await action(coordinator, *args, **kwargs):
                    _LOGGER.error(f"Failed to execute service {action.__name__} for {entity_id}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout executing service for {entity_id}")
        except Exception as ex:
            _LOGGER.error(f"Error executing Bookoo service for {entity_id}: {ex}")

    @callback
    def set_beep_level_service_handler(service_call: ServiceCall) -> None:
        """Handle set beep level service calls."""
        level = service_call.data.get("level", DEFAULT_BEEP_LEVEL)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord, lvl: coord.async_set_beep_level(lvl), level))

    @callback
    def set_auto_off_service_handler(service_call: ServiceCall) -> None:
        """Handle set auto-off timer service calls."""
        minutes = service_call.data.get("minutes", DEFAULT_AUTO_OFF_MINUTES)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord, mins: coord.async_set_auto_off_minutes(mins), minutes))

    @callback
    def set_flow_smoothing_service_handler(service_call: ServiceCall) -> None:
        """Handle set flow smoothing service calls."""
        enabled = service_call.data.get("enabled", DEFAULT_FLOW_SMOOTHING)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord, en: coord.async_set_flow_smoothing(en), enabled))

    # Register services with schemas
    # Services tare, start_timer, stop_timer, reset_timer, tare_and_start_timer are now entity services on buttons.
    hass.services.async_register(
        DOMAIN, "set_beep_level", set_beep_level_service_handler, schema=SERVICE_SCHEMA_BEEP_LEVEL
    )
    hass.services.async_register(
        DOMAIN, "set_auto_off", set_auto_off_service_handler, schema=SERVICE_SCHEMA_AUTO_OFF
    )
    hass.services.async_register(
        DOMAIN, "set_flow_smoothing", set_flow_smoothing_service_handler, 
        schema=SERVICE_SCHEMA_FLOW_SMOOTHING
    )
    
    # Register services in the UI
    platform = next((p for p in async_get_platforms(hass, DOMAIN) 
                   if p.domain == "sensor"), None)
    if platform:
        platform.async_register_entity_service(
            "tare",
            SERVICE_SCHEMA_TARE,
            "async_tare",
        )
        platform.async_register_entity_service(
            "start_timer",
            SERVICE_SCHEMA_BASE,
            "async_start_timer",
        )
        platform.async_register_entity_service(
            "stop_timer",
            SERVICE_SCHEMA_BASE,
            "async_stop_timer",
        )
        platform.async_register_entity_service(
            "reset_timer",
            SERVICE_SCHEMA_BASE,
            "async_reset_timer",
        )
        platform.async_register_entity_service(
            "tare_and_start_timer",
            SERVICE_SCHEMA_BASE,
            "async_tare_and_start_timer",
        )
        platform.async_register_entity_service(
            "set_beep_level",
            SERVICE_SCHEMA_BEEP_LEVEL,
            "async_set_beep_level",
        )
        platform.async_register_entity_service(
            "set_auto_off",
            SERVICE_SCHEMA_AUTO_OFF,
            "async_set_auto_off_minutes",
        )
        platform.async_register_entity_service(
            "set_flow_smoothing",
            SERVICE_SCHEMA_FLOW_SMOOTHING,
            "async_set_flow_smoothing",
        )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Bookoo BLE services."""
    # Services tare, start_timer, stop_timer, reset_timer, tare_and_start_timer are now entity services on buttons.
    for service in [
        "set_beep_level",
        "set_auto_off",
        "set_flow_smoothing",
    ]:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
