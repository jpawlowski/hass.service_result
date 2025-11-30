"""
Config flow for service_result.

This module implements the main configuration flow including:
- Initial user setup (service configuration)
- Reconfiguration of existing entries

The config flow features:
- Service action dropdown selector for easy service selection
- Automatic parsing of full YAML from Developer Tools
- Service validation before accepting configuration
- Cleaning of redundant data from pasted YAML
- Update mode selection (polling, manual, state trigger)

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from custom_components.service_result.config_flow_handler.schemas import get_reconfigure_schema, get_user_schema
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
    - user: Initial setup via UI (configure service to call)
    - reconfigure: Update existing configuration

    Features:
    - Service action dropdown selector for easy selection
    - Auto-detection of action from pasted YAML
    - Service validation before accepting
    - Cleaning of redundant YAML data

    For more details:
    https://developers.home-assistant.io/docs/config_entries_config_flow_handler
    """

    VERSION = 2  # Bumped for new config format

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
        Handle a flow initialized by the user.

        This is the entry point when a user adds the integration from the UI.
        User can:
        1. Select a service from the dropdown
        2. Optionally paste full YAML from Developer Tools
        3. The system auto-extracts action and cleans the data

        Action Precedence Logic:
        - If user pastes YAML containing "action:" key, that takes priority
        - The dropdown is automatically updated to match the YAML action
        - This allows users who paste full YAML to skip dropdown selection
        - If no action in YAML, the dropdown selection is used

        Args:
            user_input: The user input from the config flow form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.
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
                # Create the entry
                name = user_input.get(CONF_NAME, f"{domain}.{service_name}")
                response_path = user_input.get(CONF_RESPONSE_DATA_PATH, "")
                attribute_name = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
                update_mode = user_input.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
                scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
                trigger_entity = user_input.get(CONF_TRIGGER_ENTITY, "")
                trigger_from_state = user_input.get(CONF_TRIGGER_FROM_STATE, "")
                trigger_to_state = user_input.get(CONF_TRIGGER_TO_STATE, "")

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_SERVICE_ACTION: action_selector_data,
                        CONF_SERVICE_DATA_YAML: updated_input.get(CONF_SERVICE_DATA_YAML, clean_yaml),
                        CONF_RESPONSE_DATA_PATH: response_path,
                        CONF_ATTRIBUTE_NAME: attribute_name,
                        CONF_UPDATE_MODE: update_mode,
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_TRIGGER_ENTITY: trigger_entity,
                        CONF_TRIGGER_FROM_STATE: trigger_from_state,
                        CONF_TRIGGER_TO_STATE: trigger_to_state,
                    },
                )

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

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle reconfiguration of the integration.

        Allows users to update the service configuration without removing
        and re-adding the integration.

        Args:
            user_input: The user input from the reconfigure form, or None for initial display.

        Returns:
            The config flow result, either showing a form or updating the entry.
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
                name = user_input.get(CONF_NAME, f"{domain}.{service_name}")
                response_path = user_input.get(CONF_RESPONSE_DATA_PATH, "")
                attribute_name = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
                update_mode = user_input.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
                scan_interval = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
                trigger_entity = user_input.get(CONF_TRIGGER_ENTITY, "")
                trigger_from_state = user_input.get(CONF_TRIGGER_FROM_STATE, "")
                trigger_to_state = user_input.get(CONF_TRIGGER_TO_STATE, "")

                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_NAME: name,
                        CONF_SERVICE_ACTION: action_selector_data,
                        CONF_SERVICE_DATA_YAML: updated_input.get(CONF_SERVICE_DATA_YAML, clean_yaml),
                        CONF_RESPONSE_DATA_PATH: response_path,
                        CONF_ATTRIBUTE_NAME: attribute_name,
                        CONF_UPDATE_MODE: update_mode,
                        CONF_SCAN_INTERVAL: scan_interval,
                        CONF_TRIGGER_ENTITY: trigger_entity,
                        CONF_TRIGGER_FROM_STATE: trigger_from_state,
                        CONF_TRIGGER_TO_STATE: trigger_to_state,
                    },
                )

            if updated_input:
                user_input = {**user_input, **updated_input}

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(entry.data),
            errors=errors,
            description_placeholders=description_placeholders if description_placeholders else None,
        )


__all__ = ["ServiceResultEntitiesConfigFlowHandler"]
