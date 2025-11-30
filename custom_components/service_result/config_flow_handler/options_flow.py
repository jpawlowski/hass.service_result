"""
Options flow for service_result.

This module implements the options flow that allows users to modify settings
after the initial configuration, such as update intervals and service configuration.

For more information:
https://developers.home-assistant.io/docs/config_entries_options_flow_handler
"""

from __future__ import annotations

from typing import Any

import yaml

from custom_components.service_result.config_flow_handler.schemas import get_options_schema
from custom_components.service_result.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_DATA_YAML,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
)
from homeassistant import config_entries


class ServiceResultEntitiesOptionsFlow(config_entries.OptionsFlow):
    """
    Handle options flow for the integration.

    This class manages the options that users can modify after initial setup,
    such as update intervals and service configuration.

    For more information:
    https://developers.home-assistant.io/docs/config_entries_options_flow_handler
    """

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Manage the options for the integration.

        This is the entry point for the options flow, allowing users to
        configure the service and polling interval.

        Args:
            user_input: The user input from the options form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an options entry.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the service exists
            service_domain = user_input.get(CONF_SERVICE_DOMAIN, "")
            service_name = user_input.get(CONF_SERVICE_NAME, "")

            if not self.hass.services.has_service(service_domain, service_name):
                errors["base"] = "service_not_found"
            else:
                # Validate YAML
                service_data_yaml = user_input.get(CONF_SERVICE_DATA_YAML, "")
                if service_data_yaml:
                    try:
                        parsed = yaml.safe_load(service_data_yaml)
                        if parsed is not None and not isinstance(parsed, dict):
                            errors["base"] = "yaml_not_dict"
                    except yaml.YAMLError:
                        errors["base"] = "yaml_parse_error"

            if not errors:
                # Separate data fields from options fields
                name = user_input.get(CONF_NAME, "")
                scan_interval = user_input.get(CONF_SCAN_INTERVAL)

                # Update config entry data for name and service config
                new_data = {
                    CONF_NAME: name,
                    CONF_SERVICE_DOMAIN: service_domain,
                    CONF_SERVICE_NAME: service_name,
                    CONF_SERVICE_DATA_YAML: service_data_yaml,
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    title=name,
                )

                # Return options with scan interval
                return self.async_create_entry(
                    title="",
                    data={CONF_SCAN_INTERVAL: scan_interval},
                )

        return self.async_show_form(
            step_id="init",
            data_schema=get_options_schema(
                defaults=self.config_entry.options,
                entry_data=self.config_entry.data,
            ),
            errors=errors,
        )


__all__ = ["ServiceResultEntitiesOptionsFlow"]
