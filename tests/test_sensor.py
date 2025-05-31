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
def mock_ble_manager():
    """Create a mock BLE manager."""
    manager = MagicMock()
    manager.is_connected = True
    manager.set_notification_callback = MagicMock()
    return manager


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_config_entry, mock_ble_manager):
    """Create a test coordinator."""
    coordinator = BookooDataUpdateCoordinator(
        hass, mock_ble_manager, mock_config_entry
    )
    # Set initial data
    coordinator.data = {
        ATTR_WEIGHT: 123.4,
        ATTR_FLOW_RATE: 5.6,
        ATTR_TIMER: "01:23",
        ATTR_BATTERY_LEVEL: 85,
        "raw_timer_ms": 83000,
    }
    coordinator.last_update_success = True
    return coordinator


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
        mock_ble_manager.is_connected = False
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

    async def test_notification_handling(
        self, hass: HomeAssistant, coordinator, mock_ble_manager
    ):
        """Test handling of BLE notifications."""
        # Get the notification callback
        callback = mock_ble_manager.set_notification_callback.call_args[0][0]

        # Simulate weight notification
        weight_data = bytes([
            0x03, 0x0B,  # Header
            0x00, 0x01, 0x4C,  # Timer: 332ms
            0x00,  # Unit
            0x00,  # Weight sign
            0x00, 0x04, 0xD2,  # Weight: 12.34g
            0x00,  # Flow sign
            0x00, 0x64,  # Flow: 1.0 g/s
            0x5A,  # Battery: 90%
            0x00, 0x0A,  # Standby: 10 min
            0x02,  # Buzzer: 2
            0x01,  # Flow smoothing: on
            0x00, 0x00,  # Reserved
            0x00,  # Checksum placeholder
        ])
        # Fix checksum
        checksum = 0
        for b in weight_data[:-1]:
            checksum ^= b
        weight_data = weight_data[:-1] + bytes([checksum])

        # Call the callback
        callback(weight_data)

        # Check coordinator data was updated
        assert coordinator.data[ATTR_WEIGHT] == 12.34
        assert coordinator.data[ATTR_FLOW_RATE] == 1.0
        assert coordinator.data[ATTR_BATTERY_LEVEL] == 90

    async def test_status_notification_handling(
        self, hass: HomeAssistant, coordinator, mock_ble_manager
    ):
        """Test handling of status notifications."""
        callback = mock_ble_manager.set_notification_callback.call_args[0][0]

        # Simulate status notification (timer start)
        status_data = bytes.fromhex("030d01000000000000000000000000000000000f")
        callback(status_data)

        # Check timer status was updated
        assert coordinator.data.get("timer_status") == "started"


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
        mock_coordinator.ble_manager = MagicMock()
        mock_coordinator.ble_manager.is_connected = True

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