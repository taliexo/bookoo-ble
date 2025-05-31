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

from .const import (
    DOMAIN,
    CMD_TARE,
    CMD_START_TIMER,
    CMD_STOP_TIMER,
    CMD_RESET_TIMER,
    CMD_TARE_AND_START_TIMER,
    cmd_set_beep,
    cmd_set_auto_off,
    cmd_set_flow_smoothing,
    DEFAULT_BEEP_LEVEL,
    DEFAULT_AUTO_OFF_MINUTES,
    DEFAULT_FLOW_SMOOTHING,
)
from .sensor import BookooDataUpdateCoordinator
from .device import BookooDevice # Import BookooDevice

_LOGGER = logging.getLogger(__name__)

# Command byte values based on Bookoo protocol documentation
# Format: [PRODUCT_NUMBER, TYPE, DATA1, DATA2, DATA3, CHECKSUM]


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up Bookoo BLE services."""
    
    async def get_bookoo_device_from_entity(entity_id: str) -> BookooDevice:
        """Get coordinator from entity_id."""
        component = cast(EntityComponent, hass.data.get(SENSOR_DOMAIN))
        if not component:
            raise ValueError(f"Component {SENSOR_DOMAIN} not found")
        
        entity = component.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")
        
        # Get the coordinator from the entity
        coordinator = getattr(entity, "coordinator", None)
        if not coordinator or not isinstance(coordinator, BookooDataUpdateCoordinator):
            raise ValueError(f"Entity {entity_id} is not a Bookoo sensor or coordinator not found")
        
        bookoo_device = getattr(coordinator, "bookoo_device", None)
        if not bookoo_device or not isinstance(bookoo_device, BookooDevice):
            raise ValueError(f"BookooDevice not found on coordinator for entity {entity_id}")
            
        return bookoo_device

    # async_call_bookoo_service can be simplified or removed if handlers call device methods directly.
# For this refactor, let's have handlers call device methods directly for clarity.
        """Call a Bookoo BLE service with a specific command."""
        entity_id = service_call.data.get("entity_id")
        if not entity_id:
            _LOGGER.error("No entity_id provided for service call")
            return
        
        # If entity_id is a list, just use the first one
        if isinstance(entity_id, list):
            entity_id = entity_id[0]
        
        try:
            # This block will be replaced by direct calls in handlers
            pass
        except Exception as ex:
            _LOGGER.error("Error executing Bookoo service: %s", ex)

    async def _execute_service(entity_id_or_list: str | list[str], action: Callable[..., Awaitable[bool]], *args, **kwargs):
        entity_id = entity_id_or_list[0] if isinstance(entity_id_or_list, list) else entity_id_or_list
        if not entity_id:
            _LOGGER.error("No entity_id provided for service call")
            return
        try:
            bookoo_device = await get_bookoo_device_from_entity(entity_id)
            if not await action(bookoo_device, *args, **kwargs):
                _LOGGER.error(f"Failed to execute service {action.__name__} for {entity_id}")
        except Exception as ex:
            _LOGGER.error(f"Error executing Bookoo service {action.__name__} for {entity_id}: {ex}")

    @callback
    def tare_service_handler(service_call: ServiceCall) -> None:
        """Handle tare service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev: dev.async_tare()))

    @callback
    def start_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle start timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev: dev.async_start_timer()))

    @callback
    def stop_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle stop timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev: dev.async_stop_timer()))

    @callback
    def reset_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle reset timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev: dev.async_reset_timer()))

    @callback
    def tare_and_start_timer_service_handler(service_call: ServiceCall) -> None:
        """Handle tare and start timer service calls."""
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev: dev.async_tare_and_start_timer()))

    @callback
    def set_beep_level_service_handler(service_call: ServiceCall) -> None:
        """Handle set beep level service calls."""
        level = service_call.data.get("level", DEFAULT_BEEP_LEVEL)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev, lvl: dev.async_set_beep_level(lvl), level))

    @callback
    def set_auto_off_service_handler(service_call: ServiceCall) -> None:
        """Handle set auto-off timer service calls."""
        minutes = service_call.data.get("minutes", DEFAULT_AUTO_OFF_MINUTES)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev, mins: dev.async_set_auto_off_minutes(mins), minutes))

    @callback
    def set_flow_smoothing_service_handler(service_call: ServiceCall) -> None:
        """Handle set flow smoothing service calls."""
        enabled = service_call.data.get("enabled", DEFAULT_FLOW_SMOOTHING)
        hass.async_create_task(_execute_service(service_call.data.get("entity_id"), lambda dev, en: dev.async_set_flow_smoothing(en), enabled))

    # Register services
    hass.services.async_register(
        DOMAIN, "tare", tare_service_handler
    )
    hass.services.async_register(
        DOMAIN, "start_timer", start_timer_service_handler
    )
    hass.services.async_register(
        DOMAIN, "stop_timer", stop_timer_service_handler
    )
    hass.services.async_register(
        DOMAIN, "reset_timer", reset_timer_service_handler
    )
    hass.services.async_register(
        DOMAIN, "tare_and_start_timer", tare_and_start_timer_service_handler
    )
    hass.services.async_register(
        DOMAIN, "set_beep_level", set_beep_level_service_handler
    )
    hass.services.async_register(
        DOMAIN, "set_auto_off", set_auto_off_service_handler
    )
    hass.services.async_register(
        DOMAIN, "set_flow_smoothing", set_flow_smoothing_service_handler
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
