"""Binary sensor platform for Bookoo BLE integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, ATTR_TIMER_STATUS, ATTR_STABLE, ATTR_TARE_ACTIVE, MANUFACTURER # Assuming ATTR_STABLE and ATTR_TARE_ACTIVE will be added to const.py
from .coordinator import BookooDeviceCoordinator # For type hint


_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=ATTR_TIMER_STATUS,
        name="Timer Status",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    # Placeholder for future binary sensors if stable/tare_active are implemented
    # BinarySensorEntityDescription(
    #     key=ATTR_STABLE,
    #     name="Weight Stable",
    #     device_class=BinarySensorDeviceClass.STABILITY, # Or custom
    # ),
    # BinarySensorEntityDescription(
    #     key=ATTR_TARE_ACTIVE,
    #     name="Tare Active",
    #     device_class=BinarySensorDeviceClass.OCCUPANCY, # Or custom, e.g. 'active'
    # ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE binary sensors based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator: BookooDeviceCoordinator = coordinators["device_coordinator"]
    passive_coordinator: PassiveBluetoothProcessorCoordinator = coordinators["passive_coordinator"]

    entities = []
    for description in BINARY_SENSOR_DESCRIPTIONS:
        # Ensure device_address and device_name are available for unique_id and device_info
        # These would typically come from the config entry or a central device object
        entities.append(
            BookooPassiveBinarySensor(
                passive_coordinator,
                description,
                device_coordinator.device.address, # device_coordinator has the specific device
                device_coordinator.device.device_name,
            )
        )
    async_add_entities(entities)


class BookooPassiveBinarySensor(
    PassiveBluetoothProcessorEntity[PassiveBluetoothProcessorCoordinator],
    BinarySensorEntity,
):
    """Representation of a Bookoo BLE binary sensor updated passively."""

    def __init__(
        self,
        coordinator: PassiveBluetoothProcessorCoordinator,
        description: BinarySensorEntityDescription,
        device_address: str,
        device_name: str, # Added for explicit device_info
    ) -> None:
        """Initialize the binary sensor entity."""
        # Create entity key and pass description to parent
        entity_key = PassiveBluetoothEntityKey(description.key, device_address)
        super().__init__(coordinator, entity_key, description)

        # Set a more specific unique_id and device_info
        self._attr_unique_id = f"{DOMAIN}_{device_address}_{description.key}"
        self._attr_has_entity_name = True
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_address)},
            name=device_name,
            manufacturer=MANUFACTURER, # Assuming MANUFACTURER is in const.py
            model="Bookoo Mini Scale",    # Consistent model name
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        entity_data = self.processor.entity_data.get(self.entity_key)
        if entity_data is None:
            return None

        if self.entity_description.key == ATTR_TIMER_STATUS:
            if isinstance(entity_data, str):
                status_lower = entity_data.lower()
                if status_lower == "started":
                    return True
                if status_lower == "stopped":  # Assuming 'stopped' is the state for not running
                    return False
            _LOGGER.debug(
                "Timer status for %s received unexpected data: %s (expected 'started' or 'stopped')",
                self.entity_id,
                entity_data,
            )
            return None # Data is not a recognized string or not a string at all
        
        # Future handling for other binary sensors like ATTR_STABLE, ATTR_TARE_ACTIVE
        # if isinstance(entity_data, bool):
        #     return entity_data
        
        return None # Default for unhandled or unexpected data types

    @callback
    def _async_update_from_processor_data(
        self, update: PassiveBluetoothDataUpdate
    ) -> None:
        """Update the entity from the processor data."""
        # The PassiveBluetoothDataUpdate contains all data for the device.
        # We need to extract the specific value for this sensor's key.
        new_value = update.entity_data.get(self.entity_key)
        # is_on property will use this new_value when Home Assistant requests state.
        # We just need to tell HA that the state might have changed.
        self.async_write_ha_state()

