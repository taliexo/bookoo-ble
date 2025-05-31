"""Sensor platform for Bookoo BLE integration."""
import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

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
    ATTR_AUTO_OFF_MINUTES,
    ATTR_BATTERY_LEVEL,
    ATTR_BEEP_LEVEL,
    ATTR_FLOW_RATE,
    ATTR_FLOW_SMOOTHING,
    ATTR_STABLE,
    ATTR_TARE_ACTIVE,
    ATTR_TIMER,
    ATTR_WEIGHT,
    DOMAIN,
    UNIT_GRAMS_PER_SECOND,
)
from .coordinator import BookooDeviceCoordinator
from .models import BookooBluetoothDeviceData

_LOGGER = logging.getLogger(__name__)


@dataclass
class BookooSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for Bookoo sensors."""

    value_fn: Callable[[BookooBluetoothDeviceData], Any] = None


SENSOR_DESCRIPTIONS = [
    BookooSensorEntityDescription(
        key=ATTR_WEIGHT,
        name="Weight",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weight-gram",
        value_fn=lambda device: device.data.weight if device.data else None,
    ),
    BookooSensorEntityDescription(
        key=ATTR_FLOW_RATE,
        name="Flow Rate",
        native_unit_of_measurement=UNIT_GRAMS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-outline",
        value_fn=lambda device: device.data.flow_rate if device.data else None,
    ),
    BookooSensorEntityDescription(
        key=ATTR_TIMER,
        name="Timer",
        icon="mdi:timer-outline",
        value_fn=lambda device: device.data.timer if device.data else None,
    ),
    BookooSensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.data.battery_level if device.data else None,
    ),
    BookooSensorEntityDescription(
        key=ATTR_BEEP_LEVEL,
        name="Beep Level",
        icon="mdi:volume-high",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.data.beep_level if device.data else None,
    ),
    BookooSensorEntityDescription(
        key=ATTR_AUTO_OFF_MINUTES,
        name="Auto Off Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-off-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.data.auto_off_minutes if device.data else None,
    ),
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

    # Create a list to hold all entities
    entities = []
    
    # Create both active and passive entities
    for description in SENSOR_DESCRIPTIONS:
        # Active entities (device state polling)
        if description.key in [ATTR_WEIGHT, ATTR_FLOW_RATE, ATTR_TIMER, ATTR_BATTERY_LEVEL, ATTR_BEEP_LEVEL, ATTR_AUTO_OFF_MINUTES]:
            entities.append(
                BookooActiveSensor(
                    device_coordinator,
                    description,
                    entry.entry_id,
                )
            )
    
    # Add passive entities for attributes updated by notifications
    processor = passive_coordinator.processor
    entities.extend(
        BookooPassiveSensor(
            entry.entry_id,
            passive_coordinator,
            PassiveBluetoothEntityKey(key, device_coordinator.device.address),
        )
        for key in ["weight", "flow_rate", "timer", "battery_level", "timer_status"]
    )

    async_add_entities(entities)


class BookooActiveSensor(SensorEntity):
    """Representation of a Bookoo BLE sensor that actively polls the device."""

    entity_description: BookooSensorEntityDescription

    def __init__(
        self,
        coordinator: BookooDeviceCoordinator,
        description: BookooSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._coordinator = coordinator
        self._entry_id = entry_id
        
        # Set the unique ID using the device address and entity key
        self._attr_unique_id = f"{coordinator.device.address}_{description.key}"
        
        # Link to the device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.device.address)},
            "name": coordinator.device.device_name,
            "manufacturer": coordinator.device.manufacturer,
            "model": coordinator.device.model,
        }
        
        # Entity category is diagnostic for these sensors
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the value of the sensor."""
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self._coordinator.device)
        return None

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        # Consider the entity available if the coordinator is connected
        return self._coordinator._client is not None and self._coordinator._client.is_connected


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
        
        # Set appropriate units and device class
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
        
        # Entity category is diagnostic for these sensors
        self._attr_has_entity_name = True

    @callback
    def _async_update_from_processor_data(
        self, update: PassiveBluetoothDataUpdate
    ) -> None:
        """Update the entity from the processor data."""
        self._attr_native_value = update.entity_data.get(self.entity_key)
        super()._async_update_from_processor_data(update)
