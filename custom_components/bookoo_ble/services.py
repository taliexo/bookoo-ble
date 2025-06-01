"""Services for Bookoo BLE integration."""
import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity import EntityRegistry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_BEEP_LEVEL,
    DEFAULT_AUTO_OFF_MINUTES,
    DEFAULT_FLOW_SMOOTHING,
)
from .coordinator import BookooDeviceCoordinator

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
        entity_id = entity_id_or_list[0] if isinstance(entity_id_or_list, list) else entity_id_or_list
        if not entity_id:
            _LOGGER.error("No entity_id provided for service call")
            return
        
        try:
            async with asyncio.timeout(10):  # 10 second timeout for service execution
                coordinator = await get_bookoo_coordinator_from_entity(entity_id)
                if not await action(coordinator, *args, **kwargs):
                    _LOGGER.error(f"Failed to execute service {action.__name__} for {entity_id}")
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout executing service for {entity_id}")
        except Exception as ex:
            _LOGGER.error(f"Error executing Bookoo service for {entity_id}: {ex}")

    @callback
    def tare_service_handler(service_call: ServiceCall) -> None:
        """Handle tare service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord: coord.async_tare()))

    @callback
    def start_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle start timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord: coord.async_start_timer()))

    @callback
    def stop_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle stop timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord: coord.async_stop_timer()))

    @callback
    def reset_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle reset timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord: coord.async_reset_timer()))

    @callback
    def tare_and_start_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle tare and start timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda coord: coord.async_tare_and_start_timer()))

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

    # Register services with improved schemas
    hass.services.async_register(
        DOMAIN, "tare", tare_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        })
    )
    hass.services.async_register(
        DOMAIN, "start_timer", start_timer_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        })
    )
    hass.services.async_register(
        DOMAIN, "stop_timer", stop_timer_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        })
    )
    hass.services.async_register(
        DOMAIN, "reset_timer", reset_timer_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        })
    )
    hass.services.async_register(
        DOMAIN, "tare_and_start_timer", tare_and_start_timer_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
        })
    )
    hass.services.async_register(
        DOMAIN, "set_beep_level", set_beep_level_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
            vol.Required("level"): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
        })
    )
    hass.services.async_register(
        DOMAIN, "set_auto_off", set_auto_off_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
            vol.Required("minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
        })
    )
    hass.services.async_register(
        DOMAIN, "set_flow_smoothing", set_flow_smoothing_service_handler, schema=vol.Schema({
            vol.Required("entity_id"): cv.entity_id,
            vol.Required("enabled"): cv.boolean,
        })
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload Bookoo BLE services."""
    for service in [
        "tare", 
        "start_timer", 
        "stop_timer", 
        "reset_timer", 
        "tare_and_start_timer", 
        "set_beep_level", 
        "set_auto_off", 
        "set_flow_smoothing"
    ]:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
