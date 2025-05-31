"""Config flow for Bookoo BLE integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorOption,
)

from .const import (
    DEFAULT_AUTO_OFF_MINUTES,
    DEFAULT_BEEP_LEVEL,
    DEFAULT_FLOW_SMOOTHING,
    DEFAULT_NAME,
    DEVICE_NAME_PREFIX,
    DOMAIN,
    SERVICE_UUID,
)

_LOGGER = logging.getLogger(__name__)


class BookooConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bookoo BLE."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        # Check if already configured
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        # Store discovery info for the next step
        self._discovery_info = discovery_info
        
        # Use the device name as the default name, if available
        name = discovery_info.name or DEFAULT_NAME
        
        # Create an entry for the discovered device
        return self.async_create_entry(
            title=name,
            data={
                CONF_ADDRESS: discovery_info.address,
                CONF_NAME: name,
                "beep_level": DEFAULT_BEEP_LEVEL,
                "auto_off_minutes": DEFAULT_AUTO_OFF_MINUTES,
                "flow_smoothing": DEFAULT_FLOW_SMOOTHING,
            },
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            discovery_info = self._discovered_devices[address]
            
            # Check if already configured
            await self.async_set_unique_id(discovery_info.address)
            self._abort_if_unique_id_configured()
            
            # Use the device name as the default name, if available
            name = user_input.get(CONF_NAME, discovery_info.name or DEFAULT_NAME)
            
            # Create an entry for the selected device
            return self.async_create_entry(
                title=name,
                data={
                    CONF_ADDRESS: discovery_info.address,
                    CONF_NAME: name,
                    "beep_level": user_input.get("beep_level", DEFAULT_BEEP_LEVEL),
                    "auto_off_minutes": user_input.get("auto_off_minutes", DEFAULT_AUTO_OFF_MINUTES),
                    "flow_smoothing": user_input.get("flow_smoothing", DEFAULT_FLOW_SMOOTHING),
                },
            )

        # Get all discovered Bluetooth devices
        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass):
            # Check if this is a Bookoo device
            if (
                discovery_info.name
                and discovery_info.name.startswith(DEVICE_NAME_PREFIX)
                or SERVICE_UUID.lower() in [
                    uuid.lower() for uuid in discovery_info.service_uuids
                ]
            ):
                # Skip devices that are already configured
                if discovery_info.address in current_addresses:
                    continue
                
                # Add to the list of discovered devices
                self._discovered_devices[discovery_info.address] = discovery_info

        # Check if any devices were discovered
        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Create a list of device options for the selector
        device_options = []
        for address, discovery_info in self._discovered_devices.items():
            name = discovery_info.name or "Unknown"
            device_options.append(
                SelectSelectorOption(
                    value=address,
                    label=f"{name} ({address})",
                )
            )

        # Create the form schema
        schema = vol.Schema(
            {
                vol.Required(CONF_ADDRESS): SelectSelector(
                    SelectSelectorConfig(
                        options=device_options,
                        multiple=False,
                    )
                ),
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional("beep_level", default=DEFAULT_BEEP_LEVEL): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        max=5,
                        step=1,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional("auto_off_minutes", default=DEFAULT_AUTO_OFF_MINUTES): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=30,
                        step=1,
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
                vol.Optional("flow_smoothing", default=DEFAULT_FLOW_SMOOTHING): BooleanSelector(),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return BookooOptionsFlowHandler(config_entry)


class BookooOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Bookoo BLE options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Get current options from config entry
        options = {
            **self.config_entry.options,
        }
        
        # Use data from config entry if options are not set
        beep_level = options.get(
            "beep_level", 
            self.config_entry.data.get("beep_level", DEFAULT_BEEP_LEVEL)
        )
        auto_off_minutes = options.get(
            "auto_off_minutes", 
            self.config_entry.data.get("auto_off_minutes", DEFAULT_AUTO_OFF_MINUTES)
        )
        flow_smoothing = options.get(
            "flow_smoothing", 
            self.config_entry.data.get("flow_smoothing", DEFAULT_FLOW_SMOOTHING)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("beep_level", default=beep_level): NumberSelector(
                        NumberSelectorConfig(
                            min=0,
                            max=5,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional("auto_off_minutes", default=auto_off_minutes): NumberSelector(
                        NumberSelectorConfig(
                            min=1,
                            max=30,
                            step=1,
                            mode=NumberSelectorMode.SLIDER,
                        )
                    ),
                    vol.Optional("flow_smoothing", default=flow_smoothing): BooleanSelector(),
                }
            ),
        )
