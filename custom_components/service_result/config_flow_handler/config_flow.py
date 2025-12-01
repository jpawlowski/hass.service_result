"""
Config flow for service_result.

This module implements the main configuration flow including:
- Initial user setup (service configuration) - multi-step
- Reconfiguration of existing entries - multi-step

The config flow is organized in steps:
1. Basic configuration (Name, Service Action, Service Data YAML)
2. Update mode selection (Polling, Manual, State Trigger)
3. Mode-specific settings with collapsible advanced options

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from custom_components.service_result.config_flow_handler.schemas import (
    SECTION_ADVANCED_OPTIONS,
    get_manual_settings_schema,
    get_polling_settings_schema,
    get_reconfigure_schema,
    get_state_trigger_settings_schema,
    get_update_mode_schema,
    get_user_schema,
)
from custom_components.service_result.config_flow_handler.validators import dict_to_yaml, parse_service_yaml
from custom_components.service_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_ACTION,
    CONF_SERVICE_DATA_YAML,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UPDATE_MODE,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    DOMAIN,
    LOGGER,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
)
from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

if TYPE_CHECKING:
    from custom_components.service_result.config_flow_handler.options_flow import ServiceResultEntitiesOptionsFlow


class ServiceResultEntitiesConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle a config flow for service_result.

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
    - Service validation before accepting
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
    ) -> ServiceResultEntitiesOptionsFlow:
        """
        Get the options flow for this handler.

        Returns:
            The options flow instance for modifying integration options.
        """
        from custom_components.service_result.config_flow_handler.options_flow import (  # noqa: PLC0415
            ServiceResultEntitiesOptionsFlow,
        )

        return ServiceResultEntitiesOptionsFlow()

    def _extract_action_from_selector(self, action_data: dict[str, Any] | None) -> tuple[str, str] | None:
        """
        Extract domain and service name from action selector data.

        The action selector returns data like:
        {"action": "domain.service_name", "data": {...}, "target": {...}}

        Args:
            action_data: The action selector output dictionary.

        Returns:
            A tuple of (domain, service_name) or None if invalid.
        """
        if not action_data:
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
    ) -> tuple[bool, str | None, str | None]:
        """
        Validate that the service can be called successfully.

        This actually calls the service with return_response=True to verify
        it works before accepting the configuration.

        Args:
            domain: Service domain.
            service: Service name.
            service_data: Service data dictionary.

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
                blocking=True,
                return_response=True,
            )
        except ServiceNotFound:
            return False, "service_not_found", f"Service {domain}.{service} not found"
        except HomeAssistantError as exc:
            error_msg = str(exc)
            LOGGER.warning(
                "Service %s.%s call failed during validation: %s",
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
                # Service doesn't return data - this is acceptable
                LOGGER.debug(
                    "Service %s.%s called successfully (no response data)",
                    domain,
                    service,
                )
                return True, None, None

            LOGGER.debug(
                "Service %s.%s called successfully, response type: %s",
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
        2. Select a service from the dropdown
        3. Optionally paste full YAML from Developer Tools
        4. The system auto-extracts action and cleans the data

        Action Precedence Logic:
        - If user pastes YAML containing "action:" key, that takes priority
        - The dropdown is automatically updated to match the YAML action
        - This allows users who paste full YAML to skip dropdown selection
        - If no action in YAML, the dropdown selection is used

        Args:
            user_input: The user input from the config flow form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to next step.
        """
        errors: dict[str, str] = {}
        updated_input: dict[str, Any] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            service_data_yaml = user_input.get(CONF_SERVICE_DATA_YAML, "")
            action_selector_data = user_input.get(CONF_SERVICE_ACTION)

            # Parse the YAML to extract action and clean data
            # All service data fields (including entry_id) are preserved
            cleaned_data, yaml_action, yaml_error = parse_service_yaml(service_data_yaml)

            if yaml_error:
                errors["base"] = yaml_error
            else:
                # Determine the final action to use
                # Priority: YAML action > dropdown selection
                domain: str | None = None
                service_name: str | None = None

                if yaml_action:
                    # User pasted YAML with action - extract and use it
                    if "." in yaml_action:
                        domain, service_name = yaml_action.split(".", 1)
                        # Update the action selector to match
                        action_selector_data = {"action": yaml_action}
                        updated_input[CONF_SERVICE_ACTION] = action_selector_data
                elif action_selector_data:
                    # Use dropdown selection
                    extracted = self._extract_action_from_selector(action_selector_data)
                    if extracted:
                        domain, service_name = extracted

                if not domain or not service_name:
                    errors["base"] = "no_service_selected"
                elif not self.hass.services.has_service(domain, service_name):
                    errors["base"] = "service_not_found"
                else:
                    # Convert cleaned data back to YAML
                    clean_yaml = dict_to_yaml(cleaned_data or {})
                    updated_input[CONF_SERVICE_DATA_YAML] = clean_yaml

                    # Parse the cleaned YAML to get the actual data dict for validation
                    try:
                        validation_data = yaml.safe_load(clean_yaml) if clean_yaml else {}
                        if validation_data is None:
                            validation_data = {}
                    except yaml.YAMLError:
                        validation_data = {}

                    # Actually call the service to validate it works
                    success, error_key, error_msg = await self._validate_service_call(
                        domain, service_name, validation_data
                    )
                    if not success and error_key:
                        errors["base"] = error_key
                        if error_msg:
                            description_placeholders["error_message"] = error_msg

            if not errors:
                # Store data for next step
                name = user_input.get(CONF_NAME, f"{domain}.{service_name}")
                self._step_data = {
                    CONF_NAME: name,
                    CONF_SERVICE_ACTION: updated_input.get(CONF_SERVICE_ACTION, action_selector_data),
                    CONF_SERVICE_DATA_YAML: updated_input.get(CONF_SERVICE_DATA_YAML, clean_yaml),
                }
                # Proceed to update mode selection
                return await self.async_step_update_mode()

            # If we have updates to apply (e.g., action extracted from YAML),
            # merge them into user_input for the form defaults
            if updated_input:
                user_input = {**user_input, **updated_input}

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
            description_placeholders=description_placeholders if description_placeholders else None,
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
            The config flow result, either showing a form or proceeding to mode-specific settings.
        """
        if user_input is not None:
            update_mode = user_input.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
            self._step_data[CONF_UPDATE_MODE] = update_mode

            # Route to the appropriate settings step based on mode
            if update_mode == UPDATE_MODE_POLLING:
                return await self.async_step_polling_settings()
            if update_mode == UPDATE_MODE_STATE_TRIGGER:
                return await self.async_step_state_trigger_settings()
            # Manual mode
            return await self.async_step_manual_settings()

        return self.async_show_form(
            step_id="update_mode",
            data_schema=get_update_mode_schema(self._step_data),
        )

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
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_POLLING,
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
                },
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
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_STATE_TRIGGER,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: user_input.get(CONF_TRIGGER_ENTITY, ""),
                    CONF_TRIGGER_FROM_STATE: user_input.get(CONF_TRIGGER_FROM_STATE, ""),
                    CONF_TRIGGER_TO_STATE: user_input.get(CONF_TRIGGER_TO_STATE, ""),
                },
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
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_create_entry(
                title=self._step_data[CONF_NAME],
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_MANUAL,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
                },
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

        Args:
            user_input: The user input from the reconfigure form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to next step.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        updated_input: dict[str, Any] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            service_data_yaml = user_input.get(CONF_SERVICE_DATA_YAML, "")
            action_selector_data = user_input.get(CONF_SERVICE_ACTION)

            # Parse the YAML to extract action and clean data
            # All service data fields (including entry_id) are preserved
            cleaned_data, yaml_action, yaml_error = parse_service_yaml(service_data_yaml)

            if yaml_error:
                errors["base"] = yaml_error
            else:
                # Determine the final action to use
                domain: str | None = None
                service_name: str | None = None

                if yaml_action:
                    # User pasted YAML with action - extract and use it
                    if "." in yaml_action:
                        domain, service_name = yaml_action.split(".", 1)
                        action_selector_data = {"action": yaml_action}
                        updated_input[CONF_SERVICE_ACTION] = action_selector_data
                elif action_selector_data:
                    extracted = self._extract_action_from_selector(action_selector_data)
                    if extracted:
                        domain, service_name = extracted

                if not domain or not service_name:
                    errors["base"] = "no_service_selected"
                elif not self.hass.services.has_service(domain, service_name):
                    errors["base"] = "service_not_found"
                else:
                    # Convert cleaned data back to YAML
                    clean_yaml = dict_to_yaml(cleaned_data or {})
                    updated_input[CONF_SERVICE_DATA_YAML] = clean_yaml

                    # Parse for validation
                    try:
                        validation_data = yaml.safe_load(clean_yaml) if clean_yaml else {}
                        if validation_data is None:
                            validation_data = {}
                    except yaml.YAMLError:
                        validation_data = {}

                    # Validate the service call
                    success, error_key, error_msg = await self._validate_service_call(
                        domain, service_name, validation_data
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
                    CONF_SERVICE_ACTION: updated_input.get(CONF_SERVICE_ACTION, action_selector_data),
                    CONF_SERVICE_DATA_YAML: updated_input.get(CONF_SERVICE_DATA_YAML, clean_yaml),
                    # Preserve existing settings as defaults
                    CONF_UPDATE_MODE: entry.data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE),
                    CONF_SCAN_INTERVAL: entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    CONF_RESPONSE_DATA_PATH: entry.data.get(CONF_RESPONSE_DATA_PATH, ""),
                    CONF_ATTRIBUTE_NAME: entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
                    CONF_TRIGGER_ENTITY: entry.data.get(CONF_TRIGGER_ENTITY, ""),
                    CONF_TRIGGER_FROM_STATE: entry.data.get(CONF_TRIGGER_FROM_STATE, ""),
                    CONF_TRIGGER_TO_STATE: entry.data.get(CONF_TRIGGER_TO_STATE, ""),
                }
                # Proceed to update mode selection
                return await self.async_step_reconfigure_update_mode()

            if updated_input:
                user_input = {**user_input, **updated_input}

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(entry.data),
            errors=errors,
            description_placeholders=description_placeholders if description_placeholders else None,
        )

    async def async_step_reconfigure_update_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfigure Step 2: Update mode selection.

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
        Handle reconfigure Step 3: Polling mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_POLLING,
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
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
        Handle reconfigure Step 3: State trigger mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_STATE_TRIGGER,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: user_input.get(CONF_TRIGGER_ENTITY, ""),
                    CONF_TRIGGER_FROM_STATE: user_input.get(CONF_TRIGGER_FROM_STATE, ""),
                    CONF_TRIGGER_TO_STATE: user_input.get(CONF_TRIGGER_TO_STATE, ""),
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
        Handle reconfigure Step 3: Manual mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
        """
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            # Extract advanced options from section
            advanced = user_input.get(SECTION_ADVANCED_OPTIONS, {})
            response_path = advanced.get(CONF_RESPONSE_DATA_PATH, "")
            attribute_name = advanced.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

            return self.async_update_reload_and_abort(
                entry,
                data={
                    CONF_NAME: self._step_data[CONF_NAME],
                    CONF_SERVICE_ACTION: self._step_data[CONF_SERVICE_ACTION],
                    CONF_SERVICE_DATA_YAML: self._step_data[CONF_SERVICE_DATA_YAML],
                    CONF_UPDATE_MODE: UPDATE_MODE_MANUAL,
                    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    CONF_RESPONSE_DATA_PATH: response_path,
                    CONF_ATTRIBUTE_NAME: attribute_name,
                    CONF_TRIGGER_ENTITY: "",
                    CONF_TRIGGER_FROM_STATE: "",
                    CONF_TRIGGER_TO_STATE: "",
                },
            )

        return self.async_show_form(
            step_id="reconfigure_manual_settings",
            data_schema=get_manual_settings_schema(self._step_data),
        )


__all__ = ["ServiceResultEntitiesConfigFlowHandler"]
