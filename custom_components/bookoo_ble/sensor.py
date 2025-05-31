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
from .helpers import parse_notification, format_timer
from .ble_manager import BookooBLEManager

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
        ble_manager: BookooBLEManager,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=NOTIFICATION_TIMEOUT_SECONDS),
        )
        self.ble_manager = ble_manager
        self.config_entry = config_entry
        self._device_name = config_entry.data.get("name", "Bookoo Scale")
        self._device_address = config_entry.data["address"]
        self._last_notification_data: Optional[Dict[str, Any]] = None
        
        # Set up notification callback
        self.ble_manager.set_notification_callback(self._handle_notification)

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
    def _handle_notification(self, data: bytes) -> None:
        """Handle notification from device."""
        parsed = parse_notification(data)
        if not parsed:
            return
        
        # Update coordinator data based on message type
        if parsed.get("message_type") == "weight":
            # Full weight data update
            self._last_notification_data = {
                ATTR_WEIGHT: parsed.get("weight_g", 0),
                ATTR_FLOW_RATE: parsed.get("flow_rate_g_s", 0),
                ATTR_TIMER: format_timer(parsed.get("timer_ms", 0)),
                ATTR_BATTERY_LEVEL: parsed.get("battery_percent", 0),
                ATTR_STABLE: parsed.get("stable", False),
                ATTR_FLOW_SMOOTHING: parsed.get("flow_smoothing", False),
                ATTR_BEEP_LEVEL: parsed.get("buzzer_gear", 0),
                ATTR_AUTO_OFF_MINUTES: parsed.get("standby_minutes", 0),
                "raw_timer_ms": parsed.get("timer_ms", 0),
            }
        elif parsed.get("message_type") == "status":
            # Status update - preserve existing data and update timer status
            if self.data:
                self._last_notification_data = dict(self.data)
                self._last_notification_data["timer_status"] = parsed.get("timer_status")
            else:
                self._last_notification_data = {
                    "timer_status": parsed.get("timer_status"),
                }
        
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
        return self.coordinator.last_update_success and self.coordinator.ble_manager.is_connected

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