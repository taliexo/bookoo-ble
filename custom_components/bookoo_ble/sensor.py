"""Sensor platform for Bookoo BLE integration."""
from __future__ import annotations

import logging

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
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    UNIT_GRAMS_PER_SECOND,
    ATTR_WEIGHT,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_BATTERY_LEVEL,
)
from .coordinator import BookooDeviceCoordinator # Import for type hint

_LOGGER = logging.getLogger(__name__)

# Sensor Descriptions
SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ATTR_WEIGHT,
        name="Weight",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weight-gram",
    ),
    SensorEntityDescription(
        key=ATTR_FLOW_RATE,
        name="Flow Rate",
        native_unit_of_measurement=UNIT_GRAMS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water-outline",
    ),
    SensorEntityDescription(
        key=ATTR_TIMER,
        name="Timer",
        icon="mdi:timer-outline",
        # Timer is a string like "MM:SS", so no unit or state_class needed here
        # unless we parse it to seconds and use UnitOfTime.SECONDS
    ),
    SensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="timer_status", # From parser.py, not in const.py
        name="Timer Status",
        icon="mdi:timer-play-outline", # mdi:timer-pause-outline or mdi:timer-stop-outline could also be used
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="beep_level", # From parser.py, not in const.py
        name="Beep Level",
        icon="mdi:volume-high",
        state_class=SensorStateClass.MEASUREMENT, # Assuming it's a numeric value 0-5
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="auto_off_minutes", # From parser.py, not in const.py
        name="Auto Off Minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-off-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flow_smoothing", # From parser.py, not in const.py
        name="Flow Smoothing",
        icon="mdi:chart-line-variant", # mdi:chart-bell-curve-cumulative or mdi:tune-variant
        # This is likely a boolean, so might be better as a binary_sensor or switch
        # If it's a sensor showing 'On'/'Off', then no state_class needed.
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE sensors based on a config entry."""
    # Entities are now created dynamically by the PassiveBluetoothProcessorCoordinator
    # when data for their entity_key (from SENSOR_DESCRIPTIONS) is first pushed
    # by the BookooPassiveBluetoothDataProcessor.
    # The processor (in coordinator.py) needs to be aware of these SENSOR_DESCRIPTIONS.
    _LOGGER.debug("Bookoo BLE sensor platform setup. Entities will be created dynamically.")
    # No explicit async_add_entities(entities) here for these passive entities.


class BookooPassiveSensor(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of a Bookoo BLE sensor updated passively by notifications."""

    def __init__(
        self,
        coordinator: PassiveBluetoothProcessorCoordinator,
        description: SensorEntityDescription,
        # device_address and device_name are removed as constructor arguments
        # The entity_key passed to super() will be just description.key or a full PassiveBluetoothEntityKey
        # The base class will associate with the correct device via the coordinator and data updates.
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        # The PassiveBluetoothProcessorEntity's __init__ takes:
        # processor: PassiveBluetoothProcessorCoordinator,
        # entity_key: PassiveBluetoothEntityKey | str,
        # We provide the string key from the description. The processor handles the device association.
        super().__init__(coordinator, description.key)
        self._attr_has_entity_name = True
        # _attr_unique_id will be generated by the base class like: f"{device_id}_{self.entity_key}"
        # _attr_device_info will be populated by the base class from BluetoothServiceInfoBleak

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # An entity is available if the coordinator has data for its entity_key
        return super().available and self.processor.entity_data.get(self.entity_key) is not None

    @callback
    def _async_update_from_processor_data(
        self, update: PassiveBluetoothDataUpdate
    ) -> None:
        """Update the entity from the processor data."""
        # The PassiveBluetoothDataUpdate contains all data for the device.
        # We need to extract the specific value for this sensor's key.
        new_value = update.entity_data.get(self.entity_key)
        if new_value is not None:
            self._attr_native_value = new_value
        # Let the parent class handle the rest, like calling async_write_ha_state
        super()._async_update_from_processor_data(update)
