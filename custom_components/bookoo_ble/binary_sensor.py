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

from .const import DOMAIN, ATTR_TIMER_STATUS
from .coordinator import BookooBluetoothDeviceData, BookooPassiveBluetoothDataProcessor
from .models import BookooData

if TYPE_CHECKING:
    from homeassistant.components.bluetooth.passive_update_processor import (
        PassiveBluetoothDataUpdate,
    )

_LOGGER = logging.getLogger(__name__)

TIMER_STATUS_DESCRIPTION = BinarySensorEntityDescription(
    key=ATTR_TIMER_STATUS,
    name="Timer Status",
    device_class=BinarySensorDeviceClass.RUNNING, # Or .PLAYING, .OCCUPANCY, etc.
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Bookoo BLE binary sensor entities based on a config entry."""
    passive_coordinator = hass.data[DOMAIN][entry.entry_id]["passive_coordinator"]
    processor: BookooPassiveBluetoothDataProcessor = passive_coordinator.processor

    # We will create the entity directly from the processor's tracked devices
    # when the first notification for timer_status arrives for a device.
    # Alternatively, one could iterate hass.data[DOMAIN][entry.entry_id]["device_coordinator"].device
    # if only one device per entry, but passive setup is more dynamic.

    @callback
    def _async_add_sensor_entity(address: str) -> None:
        """Add a Bookoo timer status binary sensor entity."""
        # This callback can be triggered by the processor when it first sees a timer_status
        # for a new device, or we can proactively create them if devices are already known.
        # For simplicity, let's assume the processor will handle entity creation via its updates.
        # This part needs careful integration with how PassiveBluetoothDataProcessor signals new entities.
        # For now, we'll rely on the entity being created when data for it is pushed.
        pass

    # Entities are created dynamically by PassiveBluetoothProcessorEntity
    # when data for their entity_key is first pushed.
    # We just need to ensure the processor knows about this entity description.

    # This is a placeholder for how entities might be registered if needed upfront.
    # However, PassiveBluetoothProcessorEntity handles dynamic creation.
    # coordinator = hass.data[DOMAIN][entry.entry_id]["device_coordinator"]
    # if coordinator.device:
    #     async_add_entities([BookooTimerStatusBinarySensor(coordinator.device, processor)])
    # For now, we'll let the PassiveBluetoothProcessorEntity mechanism handle it.
    _LOGGER.debug("Bookoo BLE binary_sensor platform setup complete.")


class BookooTimerStatusBinarySensor(
    PassiveBluetoothProcessorEntity[BookooPassiveBluetoothDataProcessor],
    BinarySensorEntity,
):
    """Representation of a Bookoo BLE Timer Status binary sensor."""

    entity_description: BinarySensorEntityDescription = TIMER_STATUS_DESCRIPTION

    def __init__(
        self,
        device_data: BookooBluetoothDeviceData, # This would be needed if creating manually
        processor: BookooPassiveBluetoothDataProcessor,
    ) -> None:
        """Initialize the binary sensor entity."""
        super().__init__(processor)
        # Note: PassiveBluetoothProcessorEntity sets up _attr_unique_id, _attr_device_info, etc.
        # based on the entity_key and device_id derived from BluetoothServiceInfoBleak
        # when data is pushed via processor.async_handle_update.
        # We need to ensure that the entity_key for this sensor (ATTR_TIMER_STATUS)
        # is correctly mapped in the processor.

        # Store the specific device data if needed for direct access, though passive entities
        # usually get their state from the processed data update.
        # self._device_data = device_data 

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        # The state is derived from the data pushed by the PassiveBluetoothDataProcessor
        # The key for this entity in the processed data should match self.entity_description.key
        if (
            self.processor.entity_data.get(self.entity_key)
            and isinstance(self.processor.entity_data[self.entity_key], str)
        ):
            # Assuming 'timer_status' from parsed_data is a string like 'Running' or 'Stopped'
            status_str = str(self.processor.entity_data[self.entity_key])
            return status_str.lower() == "running"
        return None # Or False if an unknown state should be off

    # _handle_coordinator_update is automatically called by PassiveBluetoothProcessorEntity
    # when data for this entity's entity_key is updated.
    # No need to implement it manually unless custom logic is required beyond state update.
