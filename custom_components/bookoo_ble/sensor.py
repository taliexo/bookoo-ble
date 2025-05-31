"""Sensor platform for Bookoo BLE integration."""
import logging
from typing import Any, Dict, Optional, Callable
from datetime import timedelta

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.const import (
    PERCENTAGE,
    MASS_GRAMS,
    TIME_MILLISECONDS,
)

from .const import (
    DOMAIN,
    MANUFACTURER,
    ATTR_WEIGHT,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_BATTERY_LEVEL,
    ATTR_STABLE,
    ATTR_TARE_ACTIVE,
    ATTR_FLOW_SMOOTHING,
    ATTR_BEEP_LEVEL,
    ATTR_AUTO_OFF_MINUTES,
    UNIT_GRAMS,
    UNIT_GRAMS_PER_SECOND,
    UNIT_MILLISECONDS,
    UNIT_PERCENT,
    UNIT_MINUTES,
    NOTIFICATION_TIMEOUT_SECONDS,
)
from .helpers import format_timer # parse_notification is now in BookooDevice
# from .ble_manager import BookooBLEManager # No longer directly used by coordinator
from .device import BookooDevice

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key=ATTR_WEIGHT,
        name="Weight",
        native_unit_of_measurement=MASS_GRAMS,
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
    ),
    SensorEntityDescription(
        key=ATTR_BATTERY_LEVEL,
        name="Battery Level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    
    entities = []
    for description in SENSOR_DESCRIPTIONS:
        entities.append(BookooSensor(coordinator, description, config_entry))
    
    async_add_entities(entities)


class BookooDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Bookoo data."""

    def __init__(
        self,
        hass: HomeAssistant,
        bookoo_device: BookooDevice, # Changed from ble_manager
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=NOTIFICATION_TIMEOUT_SECONDS),
        )
        self.bookoo_device = bookoo_device # Store BookooDevice instance
        self.config_entry = config_entry
        self._device_name = config_entry.data.get("name", "Bookoo Scale")
        self._device_address = config_entry.data["address"]
        self._last_notification_data: Optional[Dict[str, Any]] = None
        
        # Set up notification callback on the BookooDevice instance
        self.bookoo_device.set_external_notification_callback(self._handle_notification)

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update data from device."""
        # If we have recent notification data, use it
        if self._last_notification_data:
            data = self._last_notification_data
            self._last_notification_data = None
            return data
        
        # Otherwise return the last known data or empty dict
        return self.data or {}

    @callback
    def _handle_notification(self, parsed_data: Dict[str, Any]) -> None:
        """Handle parsed notification data from BookooDevice."""
        # The data is already parsed by BookooDevice._internal_notification_handler
        if not parsed_data:
            return
        
        # We can directly use parsed_data, or re-construct if needed for _last_notification_data structure
        # For simplicity, let's assume BookooDevice provides data in the expected format
        # or we adapt here slightly.
        
        # The BookooDevice already updates its internal state.
        # The coordinator's role is to hold the data for HA entities.
        # We just need to ensure the format matches what sensors expect.

        # If BookooDevice._parse_weight_notification and _parse_status_notification
        # already structure the dict as needed by sensors (including formatted timer),
        # we can largely pass it through.

        self._last_notification_data = parsed_data
        
        # Trigger coordinator update
        self.async_set_updated_data(self._last_notification_data or {})

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_address)},
            name=self._device_name,
            manufacturer=MANUFACTURER,
            model="Bookoo Scale",
            sw_version=None,  # Could be retrieved from device
        )


class BookooSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Bookoo BLE sensor."""

    def __init__(
        self,
        coordinator: BookooDataUpdateCoordinator,
        description: SensorEntityDescription,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.bookoo_device.ble_manager.is_connected

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attributes = {}
        
        # Add all relevant attributes based on sensor type
        if self.entity_description.key == ATTR_WEIGHT:
            attributes[ATTR_STABLE] = self.coordinator.data.get(ATTR_STABLE, False)
            attributes[ATTR_TARE_ACTIVE] = self.coordinator.data.get(ATTR_TARE_ACTIVE, False)
        elif self.entity_description.key == ATTR_FLOW_RATE:
            attributes[ATTR_FLOW_SMOOTHING] = self.coordinator.data.get(ATTR_FLOW_SMOOTHING, False)
        elif self.entity_description.key == ATTR_TIMER:
            attributes["timer_ms"] = self.coordinator.data.get("raw_timer_ms", 0)
            attributes["timer_status"] = self.coordinator.data.get("timer_status", "unknown")
        elif self.entity_description.key == ATTR_BATTERY_LEVEL:
            attributes[ATTR_AUTO_OFF_MINUTES] = self.coordinator.data.get(ATTR_AUTO_OFF_MINUTES, 0)
            attributes[ATTR_BEEP_LEVEL] = self.coordinator.data.get(ATTR_BEEP_LEVEL, 0)
        
        return attributes