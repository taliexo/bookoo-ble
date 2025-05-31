"""Services for Bookoo BLE integration."""
import asyncio
import logging
from typing import Dict, Any, Callable, Awaitable, cast

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers import config_validation as cv
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN

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
        """Get coordinator from entity_id."""
        # Try both sensor and button domains
        for domain in [SENSOR_DOMAIN, BUTTON_DOMAIN]:
            component = cast(EntityComponent, hass.data.get(domain))
            if not component:
                continue
            
            entity = component.get_entity(entity_id)
            if not entity:
                continue
            
            # Get the coordinator from the entity
            coordinator = getattr(entity, "_coordinator", None)
            if coordinator and isinstance(coordinator, BookooDeviceCoordinator):
                return coordinator
        
        # If not found via entity, try to find in config entries directly
        for entry_id, coordinators in hass.data[DOMAIN].items():
            if "device_coordinator" in coordinators:
                device_coordinator = coordinators["device_coordinator"]
                if isinstance(device_coordinator, BookooDeviceCoordinator):
                    return device_coordinator
                
        raise ValueError(f"Could not find a valid Bookoo coordinator for entity {entity_id}")

    async def _execute_service(entity_id_or_list: str | list[str], action: Callable[..., Awaitable[bool]], *args, **kwargs):
        """Execute a service with the given action on the coordinator."""
        entity_id = entity_id_or_list[0] if isinstance(entity_id_or_list, list) else entity_id_or_list
        if not entity_id:
            _LOGGER.error("No entity_id provided for service call")
            return
        try:
            coordinator = await get_bookoo_coordinator_from_entity(entity_id)
            if not await action(coordinator, *args, **kwargs):
                _LOGGER.error(f"Failed to execute service {action.__name__} for {entity_id}")
        except Exception as ex:
            _LOGGER.error(f"Error executing Bookoo service {action.__name__} for {entity_id}: {ex}")

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

    # Register services
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
    if hass.services.has_service(DOMAIN, "tare"):
        hass.services.async_remove(DOMAIN, "tare")
    if hass.services.has_service(DOMAIN, "start_timer"):
        hass.services.async_remove(DOMAIN, "start_timer")
    if hass.services.has_service(DOMAIN, "stop_timer"):
        hass.services.async_remove(DOMAIN, "stop_timer")
    if hass.services.has_service(DOMAIN, "reset_timer"):
        hass.services.async_remove(DOMAIN, "reset_timer")
    if hass.services.has_service(DOMAIN, "tare_and_start_timer"):
        hass.services.async_remove(DOMAIN, "tare_and_start_timer")
    if hass.services.has_service(DOMAIN, "set_beep_level"):
        hass.services.async_remove(DOMAIN, "set_beep_level")
    if hass.services.has_service(DOMAIN, "set_auto_off"):
        hass.services.async_remove(DOMAIN, "set_auto_off")
    if hass.services.has_service(DOMAIN, "set_flow_smoothing"):
        hass.services.async_remove(DOMAIN, "set_flow_smoothing")
