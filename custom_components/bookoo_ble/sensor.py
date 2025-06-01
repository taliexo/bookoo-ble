"""Sensor platform for Bookoo BLE integration."""
import logging
from typing import Any, Dict

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_WEIGHT,
    DOMAIN,
    UNIT_GRAMS_PER_SECOND,
)

_LOGGER = logging.getLogger(__name__)

# Define sensor keys
SENSOR_KEYS = [
    ATTR_WEIGHT,
    ATTR_FLOW_RATE,
    ATTR_TIMER, 
    ATTR_BATTERY_LEVEL,
    "timer_status",
    "beep_level",
    "auto_off_minutes",
    "flow_smoothing"
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE sensors based on a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator = coordinators["device_coordinator"]
    passive_coordinator = coordinators["passive_coordinator"]

    # Create only passive entities
    entities = [
        BookooPassiveSensor(
            entry.entry_id,
            passive_coordinator,
            PassiveBluetoothEntityKey(key, device_coordinator.device.address),
        )
        for key in SENSOR_KEYS
    ]

    async_add_entities(entities)


class BookooPassiveSensor(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of a Bookoo BLE sensor updated passively by notifications."""

    def __init__(
        self,
        entry_id: str,
        coordinator: PassiveBluetoothProcessorCoordinator,
        entity_key: PassiveBluetoothEntityKey,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entity_key)
        
        # Set the entity name based on the key
        self._attr_name = entity_key.key.replace("_", " ").title()
        
        # Set appropriate units and device class based on sensor type
        if entity_key.key == ATTR_WEIGHT:
            self._attr_native_unit_of_measurement = UnitOfMass.GRAMS
            self._attr_device_class = SensorDeviceClass.WEIGHT
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:weight-gram"
        elif entity_key.key == ATTR_FLOW_RATE:
            self._attr_native_unit_of_measurement = UNIT_GRAMS_PER_SECOND
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:water-outline"
        elif entity_key.key == ATTR_TIMER:
            self._attr_icon = "mdi:timer-outline"
        elif entity_key.key == ATTR_BATTERY_LEVEL:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif entity_key.key == "timer_status":
            self._attr_icon = "mdi:timer-outline"
        elif entity_key.key == "beep_level":
            self._attr_icon = "mdi:volume-high"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif entity_key.key == "auto_off_minutes":
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:timer-off-outline"
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif entity_key.key == "flow_smoothing":
            self._attr_icon = "mdi:chart-line-variant"
        
        # Entity category is diagnostic for these sensors
        self._attr_has_entity_name = True

    @callback
    def _async_update_from_processor_data(
        self, update: PassiveBluetoothDataUpdate
    ) -> None:
        """Update the entity from the processor data."""
        self._attr_native_value = update.entity_data.get(self.entity_key)
        super()._async_update_from_processor_data(update)
