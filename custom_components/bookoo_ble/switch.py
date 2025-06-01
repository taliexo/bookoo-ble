"""Switch platform for Bookoo BLE integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ATTR_FLOW_SMOOTHING,
    MANUFACTURER,
)
from .coordinator import BookooDeviceCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BookooSwitchEntityDescription(SwitchEntityDescription):
    """Switch entity description for Bookoo switches."""

    get_value_fn: Callable[[BookooDeviceCoordinator], bool] = None
    set_value_fn: Callable[[BookooDeviceCoordinator, bool], Any] = None


SWITCH_DESCRIPTIONS = [
    BookooSwitchEntityDescription(
        key=ATTR_FLOW_SMOOTHING,
        name="Flow Smoothing",
        icon="mdi:chart-line-variant",
        entity_category=EntityCategory.CONFIG,
        get_value_fn=lambda coordinator: coordinator.device.data.flow_smoothing if coordinator.device.data else False,
        set_value_fn=lambda coordinator, value: coordinator.async_set_flow_smoothing(value),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE switch entities based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator = coordinators["device_coordinator"]

    entities = []
    for description in SWITCH_DESCRIPTIONS:
        entities.append(
            BookooSwitch(
                device_coordinator,
                description,
            )
        )

    async_add_entities(entities)


class BookooSwitch(SwitchEntity):
    """Representation of a Bookoo BLE switch entity."""

    entity_description: BookooSwitchEntityDescription

    def __init__(
        self,
        coordinator: BookooDeviceCoordinator,
        description: BookooSwitchEntityDescription,
    ) -> None:
        """Initialize the switch entity."""
        self.entity_description = description
        self._coordinator = coordinator
        
        # Set the unique ID using the domain, device address, and entity key
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device.address}_{description.key}"
        
        # Link to the device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.address)},
            name=coordinator.device.device_name,
            manufacturer=MANUFACTURER, # Use constant
            model=coordinator.device.model, # Or a constant like "Bookoo Mini Scale"
        )
        
        # Set entity properties
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return the current state."""
        if self.entity_description.get_value_fn:
            return self.entity_description.get_value_fn(self._coordinator)
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if self.entity_description.set_value_fn:
            await self.entity_description.set_value_fn(self._coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if self.entity_description.set_value_fn:
            await self.entity_description.set_value_fn(self._coordinator, False)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        # Consider the entity available if the coordinator is connected
        return self._coordinator._client is not None and self._coordinator._client.is_connected
