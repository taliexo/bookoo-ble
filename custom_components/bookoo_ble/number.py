"""Number platform for Bookoo BLE integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    ATTR_BEEP_LEVEL,
    ATTR_AUTO_OFF_MINUTES,
    MANUFACTURER,
)
from .coordinator import BookooDeviceCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BookooNumberEntityDescription(NumberEntityDescription):
    """Number entity description for Bookoo numbers."""

    get_value_fn: Callable[[BookooDeviceCoordinator], float] = None
    set_value_fn: Callable[[BookooDeviceCoordinator, float], Any] = None


NUMBER_DESCRIPTIONS = [
    BookooNumberEntityDescription(
        key=ATTR_BEEP_LEVEL,
        name="Beep Level",
        icon="mdi:volume-high",
        native_min_value=0,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        get_value_fn=lambda coordinator: coordinator.device.data.beep_level if coordinator.device.data else 0,
        set_value_fn=lambda coordinator, value: coordinator.async_set_beep_level(int(value)),
    ),
    BookooNumberEntityDescription(
        key=ATTR_AUTO_OFF_MINUTES,
        name="Auto Off Minutes",
        icon="mdi:timer-off-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        native_min_value=1,
        native_max_value=30,
        native_step=1,
        mode=NumberMode.SLIDER,
        entity_category=EntityCategory.CONFIG,
        get_value_fn=lambda coordinator: coordinator.device.data.auto_off_minutes if coordinator.device.data else 0,
        set_value_fn=lambda coordinator, value: coordinator.async_set_auto_off_minutes(int(value)),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE number entities based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator = coordinators["device_coordinator"]

    entities = []
    for description in NUMBER_DESCRIPTIONS:
        entities.append(
            BookooNumber(
                device_coordinator,
                description,
            )
        )

    async_add_entities(entities)


class BookooNumber(NumberEntity):
    """Representation of a Bookoo BLE number entity."""

    entity_description: BookooNumberEntityDescription

    def __init__(
        self,
        coordinator: BookooDeviceCoordinator,
        description: BookooNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
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
    def native_value(self) -> float:
        """Return the current value."""
        if self.entity_description.get_value_fn:
            return self.entity_description.get_value_fn(self._coordinator)
        return 0

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        if self.entity_description.set_value_fn:
            await self.entity_description.set_value_fn(self._coordinator, value)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        # Consider the entity available if the coordinator is connected
        return self._coordinator._client is not None and self._coordinator._client.is_connected
