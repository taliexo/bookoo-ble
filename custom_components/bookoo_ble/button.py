"""Button platform for Bookoo BLE integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER
from .coordinator import BookooDeviceCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BookooButtonEntityDescription(ButtonEntityDescription):
    """Button entity description for Bookoo buttons."""

    press_fn: Callable[[BookooDeviceCoordinator], Any] = None


BUTTON_DESCRIPTIONS = [
    BookooButtonEntityDescription(
        key="tare",
        name="Tare",
        icon="mdi:scale-balance",
        press_fn=lambda coordinator: coordinator.async_tare(),
    ),
    BookooButtonEntityDescription(
        key="start_timer",
        name="Start Timer",
        icon="mdi:timer-play",
        press_fn=lambda coordinator: coordinator.async_start_timer(),
    ),
    BookooButtonEntityDescription(
        key="stop_timer",
        name="Stop Timer",
        icon="mdi:timer-stop",
        press_fn=lambda coordinator: coordinator.async_stop_timer(),
    ),
    BookooButtonEntityDescription(
        key="reset_timer",
        name="Reset Timer",
        icon="mdi:timer-refresh",
        press_fn=lambda coordinator: coordinator.async_reset_timer(),
    ),
    BookooButtonEntityDescription(
        key="tare_and_start_timer",
        name="Tare and Start Timer",
        icon="mdi:timer-sync",
        press_fn=lambda coordinator: coordinator.async_tare_and_start_timer(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE buttons based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator = coordinators["device_coordinator"]

    entities = []
    for description in BUTTON_DESCRIPTIONS:
        entities.append(
            BookooButton(
                device_coordinator,
                description,
            )
        )

    async_add_entities(entities)

    # Register entity services for these buttons
    platform = hass.helpers.entity_platform.async_get_current_platform()
    for description in BUTTON_DESCRIPTIONS:
        # The service name will be the same as the button's key
        # The method called on the entity will be async_press
        platform.async_register_entity_service(
            name=description.key,
            schema={},
            func="async_press",
        )


class BookooButton(ButtonEntity):
    """Representation of a Bookoo BLE button."""

    entity_description: BookooButtonEntityDescription

    def __init__(
        self,
        coordinator: BookooDeviceCoordinator,
        description: BookooButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        self.entity_description = description
        self._coordinator = coordinator
        
        # Set the unique ID using the domain, device address, and entity key
        self._attr_unique_id = f"{DOMAIN}_{coordinator.device.address}_{description.key}"
        
        # Link to the device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.address)},
            name=coordinator.device.device_name,
            manufacturer=MANUFACTURER, # Use constant if available
            model=coordinator.device.model, # Or a constant like "Bookoo Mini Scale"
        )
        
        # Set button properties
        self._attr_has_entity_name = True
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.press_fn:
            await self.entity_description.press_fn(self._coordinator)

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        # Consider the entity available if the coordinator is connected
        return self._coordinator._client is not None and self._coordinator._client.is_connected
