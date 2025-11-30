"""
Config flow for service_result.

This module implements the main configuration flow including:
- Initial user setup (service configuration)
- Reconfiguration of existing entries

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.service_result.config_flow_handler.schemas import get_reconfigure_schema, get_user_schema
from custom_components.service_result.config_flow_handler.validators import validate_service_yaml
from custom_components.service_result.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_DATA_YAML,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)
from homeassistant import config_entries

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

    For more details:
    https://developers.home-assistant.io/docs/config_entries_config_flow_handler
    """

    VERSION = 1

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

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle a flow initialized by the user.

        This is the entry point when a user adds the integration from the UI.
        User configures which service to call and its data.

        Args:
            user_input: The user input from the config flow form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an entry.
        """
        errors: dict[str, str] = {}
        service_data_yaml = ""

        if user_input is not None:
            # Validate the service exists
            service_domain = user_input.get(CONF_SERVICE_DOMAIN, "")
            service_name = user_input.get(CONF_SERVICE_NAME, "")
            service_data_yaml = user_input.get(CONF_SERVICE_DATA_YAML, "")

            if not self.hass.services.has_service(service_domain, service_name):
                errors["base"] = "service_not_found"
            else:
                # Validate YAML
                is_valid, error_key = validate_service_yaml(service_data_yaml)
                if not is_valid and error_key is not None:
                    errors["base"] = error_key

            if not errors:
                # Create the entry
                name = user_input.get(CONF_NAME, f"{service_domain}.{service_name}")

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_SERVICE_DOMAIN: service_domain,
                        CONF_SERVICE_NAME: service_name,
                        CONF_SERVICE_DATA_YAML: service_data_yaml,
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL_SECONDS,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=get_user_schema(user_input),
            errors=errors,
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

        if user_input is not None:
            # Validate the service exists
            service_domain = user_input.get(CONF_SERVICE_DOMAIN, "")
            service_name = user_input.get(CONF_SERVICE_NAME, "")
            service_data_yaml = user_input.get(CONF_SERVICE_DATA_YAML, "")

            if not self.hass.services.has_service(service_domain, service_name):
                errors["base"] = "service_not_found"
            else:
                # Validate YAML
                is_valid, error_key = validate_service_yaml(service_data_yaml)
                if not is_valid and error_key is not None:
                    errors["base"] = error_key

            if not errors:
                name = user_input.get(CONF_NAME, f"{service_domain}.{service_name}")

                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_NAME: name,
                        CONF_SERVICE_DOMAIN: service_domain,
                        CONF_SERVICE_NAME: service_name,
                        CONF_SERVICE_DATA_YAML: service_data_yaml,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=get_reconfigure_schema(entry.data),
            errors=errors,
        )


__all__ = ["ServiceResultEntitiesConfigFlowHandler"]
