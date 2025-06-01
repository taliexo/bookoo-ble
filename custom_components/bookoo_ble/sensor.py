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
    ATTR_TIMER_STATUS,
    ATTR_BEEP_LEVEL,
    ATTR_AUTO_OFF_MINUTES,
    ATTR_FLOW_SMOOTHING,
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
        key=ATTR_TIMER_STATUS,
        name="Timer Status",
        icon="mdi:timer-play-outline", # mdi:timer-pause-outline or mdi:timer-stop-outline could also be used
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_BEEP_LEVEL,
        name="Beep Level",
        icon="mdi:volume-high",
        state_class=SensorStateClass.MEASUREMENT, # Assuming it's a numeric value 0-5
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_AUTO_OFF_MINUTES,
        name="Auto Off Minutes",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-off-outline",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key=ATTR_FLOW_SMOOTHING,
        name="Flow Smoothing",
        icon="mdi:chart-line-variant", # mdi:chart-bell-curve-cumulative or mdi:tune-variant
        # This is likely a boolean, and its state is controlled by a switch entity.
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
    coordinators = hass.data[DOMAIN][entry.entry_id]
    device_coordinator: BookooDeviceCoordinator = coordinators["device_coordinator"]
    passive_coordinator: PassiveBluetoothProcessorCoordinator = coordinators["passive_coordinator"]

    entities = []
    for description in SENSOR_DESCRIPTIONS:
        entities.append(
            BookooPassiveSensor(
                passive_coordinator,
                description,
                device_coordinator.device.address,
                device_coordinator.device.device_name,
            )
        )

    async_add_entities(entities)


class BookooPassiveSensor(PassiveBluetoothProcessorEntity, SensorEntity):
    """Representation of a Bookoo BLE sensor updated passively by notifications."""

    def __init__(
        self,
        coordinator: PassiveBluetoothProcessorCoordinator,
        description: SensorEntityDescription,
        device_address: str,
        device_name: str,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        # PassiveBluetoothProcessorEntity requires entity_key for its internal logic
        # and for _attr_unique_id generation if not overridden.
        entity_key = PassiveBluetoothEntityKey(description.key, device_address)
        super().__init__(coordinator, entity_key)

        # Set a more specific unique_id to ensure consistency
        self._attr_unique_id = f"{DOMAIN}_{device_address}_{description.key}"
        self._attr_has_entity_name = True # Uses self.entity_description.name

        # Device Info: PassiveBluetoothProcessorEntity usually sets this up
        # if the coordinator's device_info is populated. Let's ensure it is.
        # If the coordinator is BookooDeviceCoordinator, it has a 'device' attribute
        # which is BookooBluetoothDeviceData.
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_address)},
            name=device_name,
            manufacturer="Bookoo Coffee", # From const.py or device data
            model="Bookoo Mini Scale",    # From const.py or device data
        )

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
