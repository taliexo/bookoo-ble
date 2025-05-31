"""Tests for Bookoo BLE sensor platform."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.bookoo_ble.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_FLOW_RATE,
    ATTR_TIMER,
    ATTR_WEIGHT,
    DOMAIN,
    UNIT_GRAMS,
    UNIT_GRAMS_PER_SECOND,
)
from custom_components.bookoo_ble.device import BookooDevice # Corrected import location
from custom_components.bookoo_ble.sensor import (
    BookooDataUpdateCoordinator,
    BookooSensor,
    SENSOR_DESCRIPTIONS,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    return MagicMock(
        entry_id="test_entry",
        data={
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Test Bookoo Scale",
        },
    )


@pytest.fixture
def mock_bookoo_device(mock_ble_manager):
    """Create a mock BookooDevice."""
    device = MagicMock(spec=BookooDevice)
    device.ble_manager = mock_ble_manager  # Assign existing mock_ble_manager
    # This mock will be called by BookooDataUpdateCoordinator to register its _handle_notification
    device.set_external_notification_callback = MagicMock()
    return device


@pytest.fixture
def mock_ble_manager():
    """Create a mock BLE manager."""
    manager = MagicMock()
    manager.is_connected = True
    manager.set_notification_callback = MagicMock()
    return manager


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_config_entry, mock_bookoo_device):
    """Create a test coordinator."""
    # Pass mock_bookoo_device instead of mock_ble_manager
    coordinator_instance = BookooDataUpdateCoordinator(
        hass, mock_bookoo_device, mock_config_entry
    )
    # Set initial data
    coordinator_instance.data = {
        ATTR_WEIGHT: 123.4,
        ATTR_FLOW_RATE: 5.6,
        ATTR_TIMER: "01:23",
        ATTR_BATTERY_LEVEL: 85,
        "raw_timer_ms": 83000,
        "timer_status": "stopped",  # Add initial timer_status for completeness
    }
    coordinator_instance.last_update_success = True
    return coordinator_instance


class TestBookooSensor:
    """Test Bookoo sensor entity."""

    async def test_sensor_properties(
        self, hass: HomeAssistant, coordinator, mock_config_entry
    ):
        """Test sensor properties."""
        # Test weight sensor
        weight_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == ATTR_WEIGHT)
        weight_sensor = BookooSensor(coordinator, weight_desc, mock_config_entry)

        assert weight_sensor.unique_id == f"test_entry_{ATTR_WEIGHT}"
        assert weight_sensor.native_value == 123.4
        assert weight_sensor.available is True
        assert weight_sensor.device_info["identifiers"] == {(DOMAIN, "AA:BB:CC:DD:EE:FF")}

    async def test_sensor_unavailable_when_disconnected(
        self, hass: HomeAssistant, coordinator, mock_config_entry, mock_ble_manager
    ):
        """Test sensor becomes unavailable when BLE disconnected."""
        weight_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == ATTR_WEIGHT)
        weight_sensor = BookooSensor(coordinator, weight_desc, mock_config_entry)

        # Initially available
        assert weight_sensor.available is True

        # Disconnect BLE
        coordinator.bookoo_device.ble_manager.is_connected = False
        assert weight_sensor.available is False

    async def test_sensor_extra_attributes(
        self, hass: HomeAssistant, coordinator, mock_config_entry
    ):
        """Test sensor extra state attributes."""
        # Test timer sensor attributes
        timer_desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == ATTR_TIMER)
        timer_sensor = BookooSensor(coordinator, timer_desc, mock_config_entry)

        attrs = timer_sensor.extra_state_attributes
        assert attrs["timer_ms"] == 83000
        assert "timer_status" in attrs


class TestBookooDataUpdateCoordinator:
    """Test Bookoo data update coordinator."""

    async def test_handle_weight_notification(
        self, hass: HomeAssistant, coordinator: BookooDataUpdateCoordinator
    ):
        """Test handling of a parsed weight notification by the coordinator."""
        # Get the callback registered by coordinator with mock_bookoo_device
        # This callback is coordinator._handle_notification
        callback = coordinator.bookoo_device.set_external_notification_callback.call_args[0][0]
        assert callback == coordinator._handle_notification

        parsed_weight_data = {
            ATTR_WEIGHT: 12.34,
            ATTR_FLOW_RATE: 1.0,
            ATTR_TIMER: "00:05", # Example formatted timer
            "raw_timer_ms": 5000,
            ATTR_BATTERY_LEVEL: 90,
            ATTR_STABLE: False,
            ATTR_BEEP_LEVEL: 2,
            ATTR_AUTO_OFF_MINUTES: 10,
            ATTR_FLOW_SMOOTHING: True,
            "message_type": "weight",
        }

        with patch.object(coordinator, 'async_set_updated_data') as mock_set_updated_data:
            callback(parsed_weight_data) # Call _handle_notification
            mock_set_updated_data.assert_called_once_with(parsed_weight_data)
        
        assert coordinator._last_notification_data == parsed_weight_data


    async def test_handle_status_notification(
        self, hass: HomeAssistant, coordinator: BookooDataUpdateCoordinator
    ):
        """Test handling of a parsed status notification by the coordinator."""
        callback = coordinator.bookoo_device.set_external_notification_callback.call_args[0][0]
        assert callback == coordinator._handle_notification

        parsed_status_data = {
            "timer_status": "started",
            "raw_status_byte": 0x01,
            "message_type": "status",
        }
        
        with patch.object(coordinator, 'async_set_updated_data') as mock_set_updated_data:
            callback(parsed_status_data)
            mock_set_updated_data.assert_called_once_with(parsed_status_data)

        assert coordinator._last_notification_data == parsed_status_data


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant, mock_config_entry):
    """Test setting up sensor platform."""
    with patch(
        "custom_components.bookoo_ble.sensor.BookooDataUpdateCoordinator"
    ) as mock_coordinator_class:
        # Create mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.device_info = {
            "identifiers": {(DOMAIN, "AA:BB:CC:DD:EE:FF")},
            "name": "Test Scale",
        }
        mock_coordinator.data = {
            ATTR_WEIGHT: 0,
            ATTR_FLOW_RATE: 0,
            ATTR_TIMER: "00:00",
            ATTR_BATTERY_LEVEL: 100,
        }
        mock_coordinator.last_update_success = True
        # Mock BookooDevice and its ble_manager
        mock_coordinator.bookoo_device = MagicMock(spec=BookooDevice)
        mock_coordinator.bookoo_device.ble_manager = MagicMock()
        mock_coordinator.bookoo_device.ble_manager.is_connected = True

        # Store coordinator
        hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

        # Mock add entities
        async_add_entities = AsyncMock()

        # Import and call setup
        from custom_components.bookoo_ble.sensor import async_setup_entry
        await async_setup_entry(hass, mock_config_entry, async_add_entities)

        # Check entities were added
        async_add_entities.assert_called_once()
        entities = async_add_entities.call_args[0][0]
        assert len(entities) == len(SENSOR_DESCRIPTIONS)

        # Check entity types
        entity_keys = [e.entity_description.key for e in entities]
        assert ATTR_WEIGHT in entity_keys
        assert ATTR_FLOW_RATE in entity_keys
        assert ATTR_TIMER in entity_keys
        assert ATTR_BATTERY_LEVEL in entity_keys