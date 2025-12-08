"""
Config flow for action_result.

This module implements the main configuration flow including:
- Initial user setup (service configuration) - multi-step
- Reconfiguration of existing entries - multi-step

The config flow is organized in steps:
1. Basic configuration (Name, Service Action)
2. Update mode selection (Polling, Manual, State Trigger)
3. Mode-specific settings with collapsible advanced options

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import (
    get_composite_unit_schema,
    get_data_settings_schema,
    get_device_selection_schema,
    get_enum_definition_schema,
    get_enum_icons_schema,
    get_enum_translation_languages_schema,
    get_enum_translation_schema,
    get_manual_settings_schema,
    get_polling_settings_schema,
    get_reconfigure_schema,
    get_state_trigger_settings_schema,
    get_transformation_schema,
    get_update_mode_schema,
    get_user_schema,
    get_value_configuration_schema,
    get_value_path_schema,
)
from custom_components.action_result.config_flow_handler.validators import validate_value_type
from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEFINE_ENUM,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENUM_ICONS,
    CONF_ENUM_TRANSLATION_LANGUAGES,
    CONF_ENUM_TRANSLATIONS,
    CONF_ENUM_VALUES,
    CONF_ICON,
    CONF_INCLUDE_RESPONSE_DATA,
    CONF_NAME,
    CONF_PARENT_DEVICE,
    CONF_RESPONSE_DATA_PATH,
    CONF_RESPONSE_DATA_PATH_ATTRIBUTES,
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_TYPE,
    CONF_SERVICE_ACTION,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UNIT_DENOMINATOR,
    CONF_UNIT_NUMERATOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_MODE,
    CONF_VALUE_TYPE,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    DOMAIN,
    LOGGER,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
    UNIT_CUSTOM_COMPOSITE,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
    VALUE_TYPE_STRING,
)
from custom_components.action_result.helpers import detect_value_type_and_suggestions
from custom_components.action_result.utils import extract_data_at_path
from homeassistant import config_entries
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.options_flow import ActionResultEntitiesOptionsFlow


class ActionResultEntitiesConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for action_result.

    This class manages the configuration flow for the integration, including
    initial setup and reconfiguration.

    Supported flows:
    - user: Initial setup via UI (Step 1: Basic configuration)
    - update_mode: Step 2: Select update mode
    - polling_settings / state_trigger_settings / manual_settings: Step 3: Mode-specific settings
    - reconfigure: Multi-step reconfiguration of existing entries

    Features:
    - Multi-step wizard for clearer configuration
    - Service action dropdown selector for easy selection
    - Auto-detection of action from pasted YAML
    - Action validation before accepting
    - Collapsible advanced options section
    - Mode-specific settings only shown when relevant

    For more details:
    https://developers.home-assistant.io/docs/config_entries_config_flow_handler
    """

    VERSION = 2  # Bumped for new config format

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        # Store data between steps
        self._step_data: dict[str, Any] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ActionResultEntitiesOptionsFlow:
        """
        Get the options flow for this handler.

        Returns:
            The options flow instance for modifying integration options.
        """
        from custom_components.action_result.config_flow_handler.options_flow import (  # noqa: PLC0415
            ActionResultEntitiesOptionsFlow,
        )

        return ActionResultEntitiesOptionsFlow(config_entry)

    def _extract_action_from_selector(
        self, action_data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> tuple[str, str] | None:
        """
        Extract domain and service name from action selector data.

        The action selector can return data in two formats:
        - Single action: {"action": "domain.service_name", "data": {...}, "target": {...}}
        - Multiple actions (sequence): [{"action": "...", ...}, {"action": "...", ...}]

        Only single actions are supported. If multiple actions are provided, an error is raised.

        Args:
            action_data: The action selector output (dict or list of dicts).

        Returns:
            A tuple of (domain, service_name) or None if invalid.

        Raises:
            ValueError: If multiple actions are provided (not supported).
        """
        if not action_data:
            return None

        # Handle list format (sequence of actions) - reject if multiple
        if isinstance(action_data, list):
            if not action_data:
                return None
            if len(action_data) > 1:
                raise ValueError("Multiple actions are not supported. Please select only one action.")
            action_data = action_data[0]

        # Handle dict format (single action)
        if not isinstance(action_data, dict):
            return None

        action = action_data.get("action", "")
        if not action or "." not in action:
            return None

        parts = action.split(".", 1)
        return (parts[0], parts[1])

    async def _validate_service_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any],
        target: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """
        Validate that the service can be called successfully.

        This actually calls the service with return_response=True to verify
        it works before accepting the configuration.

        Args:
            domain: Action domain.
            service: Action name.
            service_data: Action data dictionary.
            target: Optional target dictionary (entity_id, device_id, area_id, etc.).

        Returns:
            A tuple of (success, error_key, error_message).
            - success: True if the service call was successful.
            - error_key: Translation key for the error (or None if successful).
            - error_message: The actual error message from the service (or None).
        """
        try:
            response = await self.hass.services.async_call(
                domain=domain,
                service=service,
                service_data=service_data,
                target=target,
                blocking=True,
                return_response=True,
            )
        except ServiceNotFound:
            return False, "service_not_found", f"Action {domain}.{service} not found"
        except HomeAssistantError as exc:
            error_msg = str(exc)
            LOGGER.warning(
                "Action %s.%s call failed during validation: %s",
                domain,
                service,
                exc,
            )
            return False, "service_call_failed", error_msg
        except Exception as exc:  # noqa: BLE001 - Log unexpected exceptions
            error_msg = str(exc)
            LOGGER.exception(
                "Unexpected error validating service %s.%s",
                domain,
                service,
            )
            return False, "service_call_failed", error_msg
        else:
            # Check if we got a valid response
            if response is None:
                # Action doesn't return data - this is acceptable
                LOGGER.debug(
                    "Action %s.%s called successfully (no response data)",
                    domain,
                    service,
                )
                return True, None, None

            LOGGER.debug(
                "Action %s.%s called successfully, response type: %s",
                domain,
                service,
                type(response).__name__,
            )
            return True, None, None

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 1: Basic configuration.

        User can:
        1. Enter a name for the sensor
        2. Select and configure a service action using the visual ActionSelector

        The ActionSelector in HA 2025.11+ includes a visual editor for service data
        with an integrated YAML view, so no separate YAML field is needed.

        Args:
            user_input: The user input from the config flow form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to next step.
        """
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            action_selector_data = user_input.get(CONF_SERVICE_ACTION)

            # Extract domain and service from the ActionSelector
            domain: str | None = None
            service_name: str | None = None
            response_variable: str | None = None

            if action_selector_data:
                try:
                    extracted = self._extract_action_from_selector(action_selector_data)
                    if extracted:
                        domain, service_name = extracted
                except ValueError:
                    # Multiple actions selected - not supported
                    errors["base"] = "multiple_actions_not_supported"

            if not errors:
                if not domain or not service_name:
                    errors["base"] = "no_service_selected"
                elif not self.hass.services.has_service(domain, service_name):
                    errors["base"] = "service_not_found"
            if not errors and domain and service_name:
                # Check if service supports returning response data
                supports_response = self.hass.services.supports_response(domain, service_name)
                if supports_response == SupportsResponse.NONE:
                    errors["base"] = "service_no_response"
                    description_placeholders["service_name"] = f"{domain}.{service_name}"
                else:
                    # Get service data, target, and response_variable from the ActionSelector
                    service_data = {}
                    target = None
                    if isinstance(action_selector_data, dict):
                        service_data = action_selector_data.get("data", {})
                        # Only set target if it has actual data
                        target_data = action_selector_data.get("target", {})
                        target = target_data if target_data else None
                        # Extract response_variable if present
                        response_variable = action_selector_data.get("response_variable")
                    elif isinstance(action_selector_data, list) and action_selector_data:
                        service_data = action_selector_data[0].get("data", {})
                        # Only set target if it has actual data
                        target_data = action_selector_data[0].get("target", {})
                        target = target_data if target_data else None
                        # Extract response_variable if present
                        response_variable = action_selector_data[0].get("response_variable")

                    # Debug logging
                    LOGGER.debug(
                        "Validating service %s.%s with data=%s, target=%s",
                        domain,
                        service_name,
                        service_data,
                        target,
                    )

                    # Actually call the service to validate it works
                    success, error_key, error_msg = await self._validate_service_call(
                        domain, service_name, service_data, target
                    )
                    if not success and error_key:
                        errors["base"] = error_key
                        if error_msg:
                            description_placeholders["error_message"] = error_msg

            if not errors:
                # Store data for next step
                name = user_input.get(CONF_NAME, f"{domain}.{service_name}")

                # Extract device_id from target if present
                device_id = target.get("device_id") if target else None

                self._step_data = {
                    CONF_NAME: name,
                    CONF_SERVICE_ACTION: action_selector_data,
                    CONF_ENTITY_CATEGORY: user_input.get(CONF_ENTITY_CATEGORY, ""),
                    "_service_domain": domain,  # Store for device filtering
                    "_target_device_id": device_id,  # Store device from target
                    "_response_variable": response_variable,  # Store for suggested attribute name
                }
                # Proceed to device selection
                return await self.async_step_device_selection()

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
            description_placeholders=description_placeholders if description_placeholders else None,
        )

    async def async_step_device_selection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 1b: Parent device selection.

        Shows only devices from the integration that owns the service.
        If integration has no devices, proceeds to next step automatically.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, proceeding to sensor type selection.
        """
        if user_input is not None:
            # Store parent device selection
            self._step_data[CONF_PARENT_DEVICE] = user_input.get(CONF_PARENT_DEVICE, "")
            # Proceed to sensor type selection
            return await self.async_step_sensor_type()

        # Get integration domain from device if we have a target device
        integration_domain = None
        target_device_id = self._step_data.get("_target_device_id")

        if target_device_id:
            # Get device registry to look up the integration
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(target_device_id)
            if device and device.identifiers:
                # Get integration domain from device identifiers
                # Device identifiers format: {(domain, unique_id), ...}
                for identifier in device.identifiers:
                    if isinstance(identifier, tuple) and len(identifier) >= 1:
                        integration_domain = identifier[0]
                        break

        # Fallback to service domain if we couldn't determine from device
        if not integration_domain:
            integration_domain = self._step_data.get("_service_domain")

        LOGGER.debug(
            "Showing device selection for integration '%s' (from device: %s)",
            integration_domain,
            target_device_id,
        )

        # Don't set defaults - let user explicitly choose or leave empty
        # Even if a device was selected in the action target, we want the user
        # to actively decide whether to associate this sensor with a device
        defaults = {}

        # Show device selection form
        return self.async_show_form(
            step_id="device_selection",
            data_schema=get_device_selection_schema(integration_domain, defaults),
        )

    async def async_step_sensor_type(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 2: Sensor type selection.

        Choose between Data Sensor (response in attributes) or Value Sensor (value as state).

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a menu or proceeding to sensor-specific settings.
        """
        # Show menu for sensor type selection
        return self.async_show_menu(
            step_id="sensor_type",
            menu_options=["data_sensor", "value_sensor"],
        )

    async def async_step_data_sensor(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Data Sensor selection from menu."""
        self._step_data[CONF_SENSOR_TYPE] = SENSOR_TYPE_DATA

        # Set default entity_category for data sensors
        if CONF_ENTITY_CATEGORY not in self._step_data:
            self._step_data[CONF_ENTITY_CATEGORY] = "diagnostic"

        return await self.async_step_data_settings()

    async def async_step_value_sensor(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Value Sensor selection from menu."""
        self._step_data[CONF_SENSOR_TYPE] = SENSOR_TYPE_VALUE
        return await self.async_step_value_path()

    async def async_step_data_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3: Data sensor settings.

        Configure response data extraction for data sensors.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to update mode.
        """
        if user_input is not None:
            # Store data sensor settings
            self._step_data[CONF_RESPONSE_DATA_PATH] = user_input.get(CONF_RESPONSE_DATA_PATH, "")
            self._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            # Proceed to update mode selection
            return await self.async_step_update_mode()

        return self.async_show_form(
            step_id="data_settings",
            data_schema=get_data_settings_schema(self._step_data),
        )

    async def async_step_value_path(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3a: Value sensor path configuration.

        User specifies the path to extract the value and optionally
        a different path for attributes.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to value configuration.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            response_path = user_input.get(CONF_RESPONSE_DATA_PATH, "")

            # Validate that the path exists by calling the service
            if response_path:
                service_action = self._step_data.get(CONF_SERVICE_ACTION)
                domain, service_name = None, None

                if service_action:
                    if isinstance(service_action, list) and service_action:
                        service_action = service_action[0]
                    if isinstance(service_action, dict):
                        action = service_action.get("action", "")
                        if "." in action:
                            domain, service_name = action.split(".", 1)

                if domain and service_name:
                    # Get service data and target
                    service_data = {}
                    target = None
                    if isinstance(self._step_data.get(CONF_SERVICE_ACTION), dict):
                        service_data = self._step_data[CONF_SERVICE_ACTION].get("data", {})
                        target_data = self._step_data[CONF_SERVICE_ACTION].get("target", {})
                        target = target_data if target_data else None
                    elif isinstance(self._step_data.get(CONF_SERVICE_ACTION), list):
                        first_action = self._step_data[CONF_SERVICE_ACTION][0]
                        service_data = first_action.get("data", {})
                        target_data = first_action.get("target", {})
                        target = target_data if target_data else None

                    try:
                        # Call the service to get response
                        response = await self.hass.services.async_call(
                            domain,
                            service_name,
                            service_data=service_data,
                            target=target,
                            blocking=True,
                            return_response=True,
                        )

                        # Try to extract the value at the specified path
                        extracted_value = extract_data_at_path(response, response_path)

                        if extracted_value is None:
                            errors["base"] = "invalid_response_path"
                        elif isinstance(extracted_value, (dict, list)):
                            # Value sensor requires a leaf node (primitive value), not a structure
                            errors["base"] = "value_path_not_leaf"
                        else:
                            # Store the extracted value for auto-detection in next step
                            self._step_data["_detected_value"] = extracted_value
                    except Exception as ex:  # noqa: BLE001
                        LOGGER.debug("Error testing value path: %s", ex)
                        errors["base"] = "value_path_test_failed"

            if not errors:
                # Store path settings
                self._step_data[CONF_RESPONSE_DATA_PATH] = response_path
                self._step_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = user_input.get(
                    CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
                )
                self._step_data[CONF_INCLUDE_RESPONSE_DATA] = user_input.get(CONF_INCLUDE_RESPONSE_DATA, False)
                # Only store attribute_name if include_response_data is enabled
                if self._step_data[CONF_INCLUDE_RESPONSE_DATA]:
                    self._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

                # Proceed to value configuration with auto-detection
                return await self.async_step_value_configuration()

        return self.async_show_form(
            step_id="value_path",
            data_schema=get_value_path_schema(self._step_data),
            errors=errors,
        )

    async def async_step_value_configuration(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3b: Value sensor configuration.

        Configure value type, unit, and device class with auto-detected suggestions.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to update mode or composite unit.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate that the detected value can be converted to the selected value type
            detected_value = self._step_data.get("_detected_value")
            selected_value_type = user_input.get(CONF_VALUE_TYPE, "")

            if detected_value is not None and selected_value_type:
                is_valid, error_key, _ = validate_value_type(detected_value, selected_value_type)
                if not is_valid:
                    errors["base"] = error_key or "value_type_mismatch"

            if not errors:
                # Check if user selected custom composite unit
                selected_unit = user_input.get(CONF_UNIT_OF_MEASUREMENT, "")
                if selected_unit == UNIT_CUSTOM_COMPOSITE:
                    # Store value type and device class, but not the unit marker
                    self._step_data[CONF_VALUE_TYPE] = user_input.get(CONF_VALUE_TYPE, "")
                    self._step_data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS, "")
                    # Route to composite unit builder
                    return await self.async_step_composite_unit()

                # Store value sensor configuration
                self._step_data[CONF_VALUE_TYPE] = user_input.get(CONF_VALUE_TYPE, "")
                self._step_data[CONF_UNIT_OF_MEASUREMENT] = selected_unit
                self._step_data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS, "")
                self._step_data[CONF_ICON] = user_input.get(CONF_ICON, "")

                # Check if value_type is string - offer enum definition
                if user_input.get(CONF_VALUE_TYPE, "") == VALUE_TYPE_STRING:
                    return await self.async_step_enum_definition()

                # Otherwise proceed to update mode selection
                return await self.async_step_update_mode()

        # Auto-detect value type and suggestions from extracted value
        detected_value = self._step_data.get("_detected_value")
        if detected_value is not None:
            suggestions = detect_value_type_and_suggestions(detected_value)
            # Pre-populate with suggestions if not already set
            if CONF_VALUE_TYPE not in self._step_data:
                self._step_data[CONF_VALUE_TYPE] = suggestions["value_type"]
            if CONF_UNIT_OF_MEASUREMENT not in self._step_data:
                self._step_data[CONF_UNIT_OF_MEASUREMENT] = suggestions["unit_of_measurement"]
            if CONF_DEVICE_CLASS not in self._step_data:
                self._step_data[CONF_DEVICE_CLASS] = suggestions["device_class"]

        return self.async_show_form(
            step_id="value_configuration",
            data_schema=get_value_configuration_schema(self._step_data),
            errors=errors,
        )

    async def async_step_composite_unit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3c: Build custom composite unit.

        Allow user to build a composite unit from numerator and denominator.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to update mode.
        """
        if user_input is not None:
            # Build composite unit string from numerator and denominator
            numerator = user_input.get(CONF_UNIT_NUMERATOR, "")
            denominator = user_input.get(CONF_UNIT_DENOMINATOR, "")

            # Build the final composite unit (e.g., "€/kWh")
            composite_unit = f"{numerator}/{denominator}"
            self._step_data[CONF_UNIT_OF_MEASUREMENT] = composite_unit

            # Proceed to update mode selection
            return await self.async_step_update_mode()

        return self.async_show_form(
            step_id="composite_unit",
            data_schema=get_composite_unit_schema(),
        )

    async def async_step_enum_definition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Enum Definition step.

        Offer user to define enum values for text value sensors.
        Only shown when value_type is "string".

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, proceeding to enum icons or update mode.
        """
        if user_input is not None:
            define_enum = user_input.get(CONF_DEFINE_ENUM, False)

            if define_enum:
                # Parse enum values from comma-separated input
                enum_values_input = user_input.get(CONF_ENUM_VALUES, "")
                enum_values = [v.strip() for v in enum_values_input.split(",") if v.strip()]

                if not enum_values:
                    # No values provided - show error and re-display form
                    return self.async_show_form(
                        step_id="enum_definition",
                        data_schema=get_enum_definition_schema(self._step_data),
                        errors={"enum_values": "enum_values_required"},
                    )

                # Store enum values
                self._step_data[CONF_DEFINE_ENUM] = True
                self._step_data[CONF_ENUM_VALUES] = enum_values
                # Proceed to enum icons configuration
                return await self.async_step_enum_icons()

            # User doesn't want enum - proceed to update mode
            self._step_data[CONF_DEFINE_ENUM] = False
            return await self.async_step_update_mode()

        return self.async_show_form(
            step_id="enum_definition",
            data_schema=get_enum_definition_schema(self._step_data),
        )

    async def async_step_enum_icons(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Enum Icons step.

        Allow user to assign icons to each enum value.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, proceeding to enum translation languages.
        """
        enum_values = self._step_data.get(CONF_ENUM_VALUES, [])

        if user_input is not None:
            # Store icon mappings (filter out empty values)
            enum_icons = {value: icon for value, icon in user_input.items() if icon}
            self._step_data[CONF_ENUM_ICONS] = enum_icons
            # Proceed to translation language selection
            return await self.async_step_enum_translation_languages()

        # Get existing icons if reconfiguring
        existing_data = self._step_data if self._step_data else {}

        return self.async_show_form(
            step_id="enum_icons",
            data_schema=get_enum_icons_schema(enum_values, existing_data),
        )

    async def async_step_enum_translation_languages(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Enum Translation Languages selection step.

        User selects which languages to translate enum values into.
        English is always included.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, proceeding to first translation step (English).
        """
        if user_input is not None:
            # Store selected languages (always include English)
            selected_languages = user_input.get(CONF_ENUM_TRANSLATION_LANGUAGES, [])
            # Ensure "en" is always first
            all_languages = ["en"] + [lang for lang in selected_languages if lang != "en"]
            self._step_data[CONF_ENUM_TRANSLATION_LANGUAGES] = all_languages
            self._step_data["_current_translation_language_index"] = 0  # Start with English
            # Proceed to first translation step (English)
            return await self.async_step_enum_translation()

        return self.async_show_form(
            step_id="enum_translation_languages",
            data_schema=get_enum_translation_languages_schema(self._step_data),
        )

    async def async_step_enum_translation(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Enum Translation step for a specific language.

        This step is dynamically repeated for each selected language.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, repeating for next language or proceeding to update mode.
        """
        languages = self._step_data.get(CONF_ENUM_TRANSLATION_LANGUAGES, ["en"])
        current_index = self._step_data.get("_current_translation_language_index", 0)
        current_language = languages[current_index]
        enum_values = self._step_data.get(CONF_ENUM_VALUES, [])

        if user_input is not None:
            # Store translations for this language
            if CONF_ENUM_TRANSLATIONS not in self._step_data:
                self._step_data[CONF_ENUM_TRANSLATIONS] = {}
            self._step_data[CONF_ENUM_TRANSLATIONS][current_language] = user_input

            # Check if there are more languages to translate
            next_index = current_index + 1
            if next_index < len(languages):
                # Move to next language
                self._step_data["_current_translation_language_index"] = next_index
                return await self.async_step_enum_translation()

            # All translations done - clean up temp data and proceed to update mode
            self._step_data.pop("_current_translation_language_index", None)
            return await self.async_step_update_mode()

        # Display form for current language
        # Get language display name
        language_names = {
            "en": "English",
            "de": "German (Deutsch)",
            "fr": "French (Français)",
            "es": "Spanish (Español)",
            "it": "Italian (Italiano)",
            "nl": "Dutch (Nederlands)",
            "pl": "Polish (Polski)",
            "pt": "Portuguese (Português)",
            "ru": "Russian (Русский)",
            "sv": "Swedish (Svenska)",
            "da": "Danish (Dansk)",
            "nb": "Norwegian (Norsk)",
            "fi": "Finnish (Suomi)",
            "cs": "Czech (Čeština)",
            "sk": "Slovak (Slovenčina)",
            "hu": "Hungarian (Magyar)",
            "ro": "Romanian (Română)",
            "bg": "Bulgarian (Български)",
            "hr": "Croatian (Hrvatski)",
            "sl": "Slovenian (Slovenščina)",
            "el": "Greek (Ελληνικά)",
        }
        language_name = language_names.get(current_language, current_language)

        return self.async_show_form(
            step_id="enum_translation",
            data_schema=get_enum_translation_schema(current_language, enum_values, self._step_data),
            description_placeholders={"language": str(language_name)},
        )

    async def async_step_transformation(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 2: Transformation configuration.

        Configure how the service response is extracted and exposed.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to update mode.
        """
        if user_input is not None:
            # Store transformation settings
            self._step_data[CONF_RESPONSE_DATA_PATH] = user_input.get(CONF_RESPONSE_DATA_PATH, "")
            self._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            # Proceed to update mode selection
            return await self.async_step_update_mode()

        return self.async_show_form(
            step_id="transformation",
            data_schema=get_transformation_schema(self._step_data),
        )

    async def async_step_update_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 2: Update mode selection.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, showing a menu for update mode selection.
        """
        # Show menu for update mode selection
        return self.async_show_menu(
            step_id="update_mode",
            menu_options=["polling_mode", "state_trigger_mode", "manual_mode"],
        )

    async def async_step_polling_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Polling mode selection from menu."""
        self._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_POLLING
        return await self.async_step_polling_settings()

    async def async_step_state_trigger_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle State Trigger mode selection from menu."""
        self._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_STATE_TRIGGER
        return await self.async_step_state_trigger_settings()

    async def async_step_manual_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Manual mode selection from menu."""
        self._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_MANUAL
        return await self.async_step_manual_settings()

    async def async_step_polling_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3: Polling mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.
        """
        if user_input is not None:
            # Build entry data based on sensor type
            sensor_type = self._step_data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)

            entry_data: dict[str, Any] = {
                CONF_NAME: self._step_data[CONF_NAME],
                CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                CONF_SENSOR_TYPE: sensor_type,
                CONF_UPDATE_MODE: UPDATE_MODE_POLLING,
                CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                CONF_TRIGGER_ENTITY: "",
                CONF_TRIGGER_FROM_STATE: "",
                CONF_TRIGGER_TO_STATE: "",
                CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
            }

            # Add sensor-type specific fields
            if sensor_type == SENSOR_TYPE_VALUE:
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = self._step_data.get(
                    CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
                )
                entry_data[CONF_VALUE_TYPE] = self._step_data.get(CONF_VALUE_TYPE, "")
                entry_data[CONF_UNIT_OF_MEASUREMENT] = self._step_data.get(CONF_UNIT_OF_MEASUREMENT, "")
                entry_data[CONF_DEVICE_CLASS] = self._step_data.get(CONF_DEVICE_CLASS, "")
                entry_data[CONF_ICON] = self._step_data.get(CONF_ICON, "")
                entry_data[CONF_INCLUDE_RESPONSE_DATA] = self._step_data.get(CONF_INCLUDE_RESPONSE_DATA, False)
                # Only include attribute_name if include_response_data is enabled
                if entry_data[CONF_INCLUDE_RESPONSE_DATA]:
                    entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
                # Add enum data if defined
                if self._step_data.get(CONF_DEFINE_ENUM, False):
                    entry_data[CONF_DEFINE_ENUM] = True
                    entry_data[CONF_ENUM_VALUES] = self._step_data.get(CONF_ENUM_VALUES, [])
                    entry_data[CONF_ENUM_ICONS] = self._step_data.get(CONF_ENUM_ICONS, {})
                    entry_data[CONF_ENUM_TRANSLATIONS] = self._step_data.get(CONF_ENUM_TRANSLATIONS, {})
            else:  # Data sensor
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data=entry_data,
            )

        return self.async_show_form(
            step_id="polling_settings",
            data_schema=get_polling_settings_schema(self._step_data),
        )

    async def async_step_state_trigger_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3: State trigger mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.
        """
        if user_input is not None:
            # Build entry data based on sensor type
            sensor_type = self._step_data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)

            entry_data: dict[str, Any] = {
                CONF_NAME: self._step_data[CONF_NAME],
                CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                CONF_SENSOR_TYPE: sensor_type,
                CONF_UPDATE_MODE: UPDATE_MODE_STATE_TRIGGER,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                CONF_TRIGGER_ENTITY: user_input.get(CONF_TRIGGER_ENTITY, ""),
                CONF_TRIGGER_FROM_STATE: user_input.get(CONF_TRIGGER_FROM_STATE, ""),
                CONF_TRIGGER_TO_STATE: user_input.get(CONF_TRIGGER_TO_STATE, ""),
                CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
            }

            # Add sensor-type specific fields
            if sensor_type == SENSOR_TYPE_VALUE:
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = self._step_data.get(
                    CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
                )
                entry_data[CONF_VALUE_TYPE] = self._step_data.get(CONF_VALUE_TYPE, "")
                entry_data[CONF_UNIT_OF_MEASUREMENT] = self._step_data.get(CONF_UNIT_OF_MEASUREMENT, "")
                entry_data[CONF_DEVICE_CLASS] = self._step_data.get(CONF_DEVICE_CLASS, "")
                entry_data[CONF_ICON] = self._step_data.get(CONF_ICON, "")
                entry_data[CONF_INCLUDE_RESPONSE_DATA] = self._step_data.get(CONF_INCLUDE_RESPONSE_DATA, False)
                # Only include attribute_name if include_response_data is enabled
                if entry_data[CONF_INCLUDE_RESPONSE_DATA]:
                    entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
                # Add enum data if defined
                if self._step_data.get(CONF_DEFINE_ENUM, False):
                    entry_data[CONF_DEFINE_ENUM] = True
                    entry_data[CONF_ENUM_VALUES] = self._step_data.get(CONF_ENUM_VALUES, [])
                    entry_data[CONF_ENUM_ICONS] = self._step_data.get(CONF_ENUM_ICONS, {})
                    entry_data[CONF_ENUM_TRANSLATIONS] = self._step_data.get(CONF_ENUM_TRANSLATIONS, {})
            else:  # Data sensor
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data=entry_data,
            )

        return self.async_show_form(
            step_id="state_trigger_settings",
            data_schema=get_state_trigger_settings_schema(self._step_data),
        )

    async def async_step_manual_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle Step 3: Manual mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.
        """
        if user_input is not None:
            # Build entry data based on sensor type
            sensor_type = self._step_data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)

            entry_data: dict[str, Any] = {
                CONF_NAME: self._step_data[CONF_NAME],
                CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                CONF_SENSOR_TYPE: sensor_type,
                CONF_UPDATE_MODE: UPDATE_MODE_MANUAL,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                CONF_TRIGGER_ENTITY: "",
                CONF_TRIGGER_FROM_STATE: "",
                CONF_TRIGGER_TO_STATE: "",
                CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
            }

            # Add sensor-type specific fields
            if sensor_type == SENSOR_TYPE_VALUE:
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = self._step_data.get(
                    CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
                )
                entry_data[CONF_VALUE_TYPE] = self._step_data.get(CONF_VALUE_TYPE, "")
                entry_data[CONF_UNIT_OF_MEASUREMENT] = self._step_data.get(CONF_UNIT_OF_MEASUREMENT, "")
                entry_data[CONF_DEVICE_CLASS] = self._step_data.get(CONF_DEVICE_CLASS, "")
                entry_data[CONF_ICON] = self._step_data.get(CONF_ICON, "")
                entry_data[CONF_INCLUDE_RESPONSE_DATA] = self._step_data.get(CONF_INCLUDE_RESPONSE_DATA, False)
                # Only include attribute_name if include_response_data is enabled
                if entry_data[CONF_INCLUDE_RESPONSE_DATA]:
                    entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
                # Add enum data if defined
                if self._step_data.get(CONF_DEFINE_ENUM, False):
                    entry_data[CONF_DEFINE_ENUM] = True
                    entry_data[CONF_ENUM_VALUES] = self._step_data.get(CONF_ENUM_VALUES, [])
                    entry_data[CONF_ENUM_ICONS] = self._step_data.get(CONF_ENUM_ICONS, {})
                    entry_data[CONF_ENUM_TRANSLATIONS] = self._step_data.get(CONF_ENUM_TRANSLATIONS, {})
            else:  # Data sensor
                entry_data[CONF_RESPONSE_DATA_PATH] = self._step_data.get(CONF_RESPONSE_DATA_PATH, "")
                entry_data[CONF_ATTRIBUTE_NAME] = self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data=entry_data,
            )

        return self.async_show_form(
            step_id="manual_settings",
            data_schema=get_manual_settings_schema(self._step_data),
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfiguration Step 1: Basic configuration.

        Allows users to update the service configuration without removing
        and re-adding the integration.

        The ActionSelector in HA 2025.11+ includes a visual editor for service data
        with an integrated YAML view, so no separate YAML field is needed.

        Args:
            user_input: The user input from the reconfigure form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to next step.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            action_selector_data = user_input.get(CONF_SERVICE_ACTION)

            # Extract domain and service from the ActionSelector
            domain: str | None = None
            service_name: str | None = None

            if action_selector_data:
                try:
                    extracted = self._extract_action_from_selector(action_selector_data)
                    if extracted:
                        domain, service_name = extracted
                except ValueError:
                    # Multiple actions selected - not supported
                    errors["base"] = "multiple_actions_not_supported"

            if not errors:
                if not domain or not service_name:
                    errors["base"] = "no_service_selected"
                elif not self.hass.services.has_service(domain, service_name):
                    errors["base"] = "service_not_found"
                else:
                    # Check if service supports returning response data
                    supports_response = self.hass.services.supports_response(domain, service_name)
                    if supports_response == SupportsResponse.NONE:
                        errors["base"] = "service_no_response"

            if not errors and domain and service_name:
                # Get service data, target, and response_variable from the ActionSelector
                service_data = {}
                target = None
                response_variable = None
                if isinstance(action_selector_data, dict):
                    service_data = action_selector_data.get("data", {})
                    # Only set target if it has actual data
                    target_data = action_selector_data.get("target", {})
                    target = target_data if target_data else None
                    # Extract response_variable if present
                    response_variable = action_selector_data.get("response_variable")
                elif isinstance(action_selector_data, list) and action_selector_data:
                    service_data = action_selector_data[0].get("data", {})
                    # Only set target if it has actual data
                    target_data = action_selector_data[0].get("target", {})
                    target = target_data if target_data else None
                    # Extract response_variable if present
                    response_variable = action_selector_data[0].get("response_variable")

                # Validate the service call
                success, error_key, error_msg = await self._validate_service_call(
                    domain, service_name, service_data, target
                )
                if not success and error_key:
                    errors["base"] = error_key
                    if error_msg:
                        description_placeholders["error_message"] = error_msg

            if not errors:
                # Store data for next step, preserving existing values
                # Note: Name is preserved from entry.data - it cannot be changed in reconfigure.
                # Users should use Home Assistant's built-in renaming mechanism instead.
                self._step_data = {
                    CONF_NAME: entry.data.get(CONF_NAME, entry.title),
                    CONF_SERVICE_ACTION: action_selector_data,
                    CONF_PARENT_DEVICE: user_input.get(CONF_PARENT_DEVICE, ""),
                    CONF_ENTITY_CATEGORY: user_input.get(CONF_ENTITY_CATEGORY, ""),
                    # Preserve existing transformation settings for the next step
                    CONF_RESPONSE_DATA_PATH: entry.data.get(CONF_RESPONSE_DATA_PATH, ""),
                    CONF_ATTRIBUTE_NAME: entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
                    # Preserve existing mode settings for later steps
                    CONF_UPDATE_MODE: entry.data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE),
                    CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    CONF_TRIGGER_ENTITY: entry.data.get(CONF_TRIGGER_ENTITY, ""),
                    CONF_TRIGGER_FROM_STATE: entry.data.get(CONF_TRIGGER_FROM_STATE, ""),
                    CONF_TRIGGER_TO_STATE: entry.data.get(CONF_TRIGGER_TO_STATE, ""),
                    "_response_variable": response_variable,  # Store for suggested attribute name
                }
                # Proceed to transformation configuration
                return await self.async_step_reconfigure_transformation()

        # Extract integration domain for device filtering
        integration_domain = None
        service_action = entry.data.get(CONF_SERVICE_ACTION)
        if service_action:
            try:
                extracted = self._extract_action_from_selector(service_action)
                if extracted:
                    integration_domain = extracted[0]
            except ValueError:
                # Multiple actions in stored data - shouldn't happen, but handle gracefully
                pass

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(entry.data, integration_domain),
            errors=errors,
            description_placeholders=description_placeholders if description_placeholders else None,
        )

    async def async_step_reconfigure_transformation(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 2: Transformation configuration.

        Configure how the service response is extracted and exposed.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to update mode.
        """
        if user_input is not None:
            # Store transformation settings
            self._step_data[CONF_RESPONSE_DATA_PATH] = user_input.get(CONF_RESPONSE_DATA_PATH, "")
            self._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            # Proceed to update mode selection
            return await self.async_step_reconfigure_update_mode()

        return self.async_show_form(
            step_id="reconfigure_transformation",
            data_schema=get_transformation_schema(self._step_data),
        )

    async def async_step_reconfigure_update_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 3: Update mode selection.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to mode-specific settings.
        """
        if user_input is not None:
            update_mode = user_input.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
            self._step_data[CONF_UPDATE_MODE] = update_mode

            # Route to the appropriate settings step based on mode
            if update_mode == UPDATE_MODE_POLLING:
                return await self.async_step_reconfigure_polling_settings()
            if update_mode == UPDATE_MODE_STATE_TRIGGER:
                return await self.async_step_reconfigure_state_trigger_settings()
            # Manual mode
            return await self.async_step_reconfigure_manual_settings()

        return self.async_show_form(
            step_id="reconfigure_update_mode",
            data_schema=get_update_mode_schema(self._step_data),
        )

    async def async_step_reconfigure_polling_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 4: Polling mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_UPDATE_MODE: UPDATE_MODE_POLLING,
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    CONF_RESPONSE_DATA_PATH: self._step_data.get(CONF_RESPONSE_DATA_PATH, ""),
                    CONF_ATTRIBUTE_NAME: self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
                    CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                    CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
                },
            )

        return self.async_show_form(
            step_id="reconfigure_polling_settings",
            data_schema=get_polling_settings_schema(self._step_data),
        )

    async def async_step_reconfigure_state_trigger_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 4: State trigger mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_UPDATE_MODE: UPDATE_MODE_STATE_TRIGGER,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: self._step_data.get(CONF_RESPONSE_DATA_PATH, ""),
                    CONF_ATTRIBUTE_NAME: self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
                    CONF_TRIGGER_ENTITY: user_input.get(CONF_TRIGGER_ENTITY, ""),
                    CONF_TRIGGER_FROM_STATE: user_input.get(CONF_TRIGGER_FROM_STATE, ""),
                    CONF_TRIGGER_TO_STATE: user_input.get(CONF_TRIGGER_TO_STATE, ""),
                    CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                    CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
                },
            )

        return self.async_show_form(
            step_id="reconfigure_state_trigger_settings",
            data_schema=get_state_trigger_settings_schema(self._step_data),
        )

    async def async_step_reconfigure_manual_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 4: Manual mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_UPDATE_MODE: UPDATE_MODE_MANUAL,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: self._step_data.get(CONF_RESPONSE_DATA_PATH, ""),
                    CONF_ATTRIBUTE_NAME: self._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
                    CONF_PARENT_DEVICE: self._step_data.get(CONF_PARENT_DEVICE, ""),
                    CONF_ENTITY_CATEGORY: self._step_data.get(CONF_ENTITY_CATEGORY, ""),
                },
            )

        return self.async_show_form(
            step_id="reconfigure_manual_settings",
            data_schema=get_manual_settings_schema(self._step_data),
        )


__all__ = ["ActionResultEntitiesConfigFlowHandler"]
