"""Tests for Bookoo BLE sensor platform."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
)
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
)
from custom_components.bookoo_ble.coordinator import (
    BookooDeviceCoordinator,
    BookooPassiveBluetoothDataProcessor,
)
from custom_components.bookoo_ble.models import BookooBluetoothDeviceData, BookooData
from custom_components.bookoo_ble.sensor import BookooPassiveSensor


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "Test Bookoo Scale",
    }
    return entry


@pytest.fixture
def mock_device_data():
    """Create mock device data."""
    service_info = MagicMock()
    service_info.address = "AA:BB:CC:DD:EE:FF"
    service_info.name = "Test Bookoo Scale"
    
    return BookooBluetoothDeviceData(
        address="AA:BB:CC:DD:EE:FF",
        device_name="Test Bookoo Scale",
        model="Bookoo Mini Scale",
        manufacturer="Bookoo Coffee",
        service_info=service_info,
        data=BookooData(
            weight=150.0,
            flow_rate=3.2,
            timer="01:15",
            raw_timer_ms=75000,
            battery_level=80,
            beep_level=3,
            auto_off_minutes=5,
            flow_smoothing=True,
            timer_status="started",
        ),
    )


@pytest.fixture
def mock_passive_processor():
    """Create a mock passive processor."""
    processor = MagicMock(spec=BookooPassiveBluetoothDataProcessor)
    return processor


@pytest.fixture
def mock_passive_coordinator(mock_passive_processor):
    """Create a mock passive coordinator."""
    coordinator = MagicMock(spec=PassiveBluetoothProcessorCoordinator)
    coordinator.processor = mock_passive_processor
    return coordinator


@pytest.fixture
def mock_device_coordinator(hass, mock_device_data, mock_passive_coordinator):
    """Create a mock device coordinator."""
    coordinator = MagicMock(spec=BookooDeviceCoordinator)
    coordinator.device = mock_device_data
    coordinator.passive_coordinator = mock_passive_coordinator
    coordinator._client = MagicMock()
    coordinator._client.is_connected = True
    return coordinator


class TestBookooPassiveSensor:
    """Test Bookoo passive sensor entity."""

    async def test_sensor_properties(self, hass):
        """Test sensor properties."""
        entity_key = PassiveBluetoothEntityKey(
            key=ATTR_WEIGHT,
            device_id="AA:BB:CC:DD:EE:FF",
        )
        
        mock_coordinator = MagicMock(spec=PassiveBluetoothProcessorCoordinator)
        
        sensor = BookooPassiveSensor(
            entry_id="test_entry_id",
            coordinator=mock_coordinator,
            entity_key=entity_key,
        )
        
        # Test entity attributes
        assert sensor.unique_id == "AA:BB:CC:DD:EE:FF_weight"
        assert sensor.name == "Weight"
        assert sensor.native_unit_of_measurement == "g"

    async def test_sensor_update_from_data(self, hass):
        """Test sensor updates from processor data."""
        entity_key = PassiveBluetoothEntityKey(
            key=ATTR_WEIGHT,
            device_id="AA:BB:CC:DD:EE:FF",
        )
        
        mock_coordinator = MagicMock(spec=PassiveBluetoothProcessorCoordinator)
        
        sensor = BookooPassiveSensor(
            entry_id="test_entry_id",
            coordinator=mock_coordinator,
            entity_key=entity_key,
        )
        
        # Create an update with data
        update = PassiveBluetoothDataUpdate(
            devices={},
            entity_descriptions={},
            entity_data={entity_key: 123.45},
            entity_names={},
            entity_pictures={},
        )
        
        # Update the sensor
        sensor._async_update_from_processor_data(update)
        
        # Check that the sensor was updated
        assert sensor.native_value == 123.45

    async def test_sensor_availability(self, hass):
        """Test sensor availability based on coordinator state."""
        entity_key = PassiveBluetoothEntityKey(
            key=ATTR_BATTERY_LEVEL,
            device_id="AA:BB:CC:DD:EE:FF",
        )
        
        mock_coordinator = MagicMock(spec=PassiveBluetoothProcessorCoordinator)
        mock_coordinator.available = True
        
        sensor = BookooPassiveSensor(
            entry_id="test_entry_id",
            coordinator=mock_coordinator,
            entity_key=entity_key,
        )
        
        # Should be available when coordinator is available
        assert sensor.available is True
        
        # Should be unavailable when coordinator is unavailable
        mock_coordinator.available = False
        assert sensor.available is False


async def test_async_setup_entry(hass, mock_config_entry, mock_device_coordinator, mock_passive_coordinator):
    """Test setting up sensor platform."""
    # Mock the async_forward_entry_setups function
    with patch("homeassistant.config_entries.ConfigEntry.async_forward_entry_setups"), \
         patch("custom_components.bookoo_ble.sensor.async_add_entities") as mock_async_add_entities:
        
        # Set up the coordinators in hass.data
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = {
            "device_coordinator": mock_device_coordinator,
            "passive_coordinator": mock_passive_coordinator,
        }
        
        # Set up the sensor entry
        from custom_components.bookoo_ble.sensor import async_setup_entry
        await async_setup_entry(hass, mock_config_entry, mock_async_add_entities)
        
        # Check that async_add_entities was called
        assert mock_async_add_entities.call_count == 1
        
        # Get the entities that were added
        entities = mock_async_add_entities.call_args[0][0]
        
        # Verify that 8 entities were created (one for each sensor key)
        assert len(entities) == 8
        
        # Verify that all entities are BookooPassiveSensor instances
        for entity in entities:
            assert isinstance(entity, BookooPassiveSensor)
