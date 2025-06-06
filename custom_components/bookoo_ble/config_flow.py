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


@config_entries.HANDLERS.register(DOMAIN)
class BookooConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bookoo BLE."""

    VERSION = 1
    MINOR_VERSION = 1

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

        # Store discovery info for the confirm step
        self._discovery_info = discovery_info
        
        # Proceed to the confirmation step
        return await self.async_step_bluetooth_confirm()

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
            # No devices found, offer to configure manually
            _LOGGER.debug("No Bookoo BLE devices found during user scan, offering manual entry.")
            return self.async_show_form(
                step_id="manual", # Transition to manual step
                data_schema=vol.Schema({
                    vol.Required(CONF_ADDRESS): str,
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                }),
                description_placeholders={"message": "No devices found. You can enter the MAC address manually."}
            )
            # Alternative: return self.async_abort(reason="no_devices_found") if manual entry is not desired here

        # Create a list of device options for the selector
        device_options = []
        for address, discovery_info in self._discovered_devices.items():
            name = discovery_info.name or "Unknown"
            device_options.append({
                "value": address,
                "label": f"{name} ({address})"
            })

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

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation of Bluetooth discovery."""
        _LOGGER.debug(
            "Entering async_step_bluetooth_confirm with user_input: %s", user_input
        )

        if self._discovery_info is None:
            _LOGGER.error(
                "'_discovery_info' is None in async_step_bluetooth_confirm. "
                "This indicates the discovery data was lost. Aborting."
            )
            return self.async_abort(reason="discovery_info_missing")

        discovery_info = self._discovery_info
        # Use discovery_info.name or DEFAULT_NAME for both title and CONF_NAME in data
        device_name = discovery_info.name or DEFAULT_NAME

        if user_input is not None:
            # User has confirmed the device
            _LOGGER.debug(
                "User confirmed Bluetooth device: %s (%s). Creating entry.",
                device_name,
                discovery_info.address,
            )
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_ADDRESS: discovery_info.address,
                    CONF_NAME: device_name,  # Store name in data as per user_step
                    "beep_level": DEFAULT_BEEP_LEVEL,
                    "auto_off_minutes": DEFAULT_AUTO_OFF_MINUTES,
                    "flow_smoothing": DEFAULT_FLOW_SMOOTHING,
                },
            )

        # user_input is None, so show the confirmation form
        self.context["title_placeholders"] = {
            "name": device_name,
            "address": discovery_info.address
        }
        self._set_confirm_only() # Makes it a simple confirm/cancel dialog
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={
                "name": device_name,
                "address": discovery_info.address
            },
            # No data_schema needed for a simple confirmation dialog
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the manual entry step for MAC address."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS].upper()  # Normalize to uppercase
            name = user_input.get(CONF_NAME, DEFAULT_NAME)

            # Basic MAC address validation (can be improved)
            # Validates XX:XX:XX:XX:XX:XX format after uppercasing
            if not (isinstance(address, str) and len(address) == 17 and address.count(':') == 5):
                # Further validation could check for valid hex characters if needed
                errors["base"] = "invalid_mac_address"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()

                _LOGGER.info("Creating entry for manually configured Bookoo BLE device: %s (%s)", name, address)
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_ADDRESS: address,
                        CONF_NAME: name,
                        "beep_level": user_input.get("beep_level", DEFAULT_BEEP_LEVEL),
                        "auto_off_minutes": user_input.get("auto_off_minutes", DEFAULT_AUTO_OFF_MINUTES),
                        "flow_smoothing": user_input.get("flow_smoothing", DEFAULT_FLOW_SMOOTHING),
                    },
                )
        
        # Show form for manual entry
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({
                vol.Required(CONF_ADDRESS): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
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
            }),
            errors=errors,
            description_placeholders={"message": "Enter the MAC address of your Bookoo scale."}
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
        # self.config_entry is now set by the parent class

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
