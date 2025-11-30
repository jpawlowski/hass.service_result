"""
Options flow for service_result.

This module implements the options flow that allows users to modify the
polling interval after initial configuration.

Service configuration changes should be done via the Reconfigure flow,
not the Options flow. This follows the Home Assistant pattern where
data contains core configuration and options contains adjustable settings.

For more information:
https://developers.home-assistant.io/docs/config_entries_options_flow_handler
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.service_result.const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS
from homeassistant import config_entries
from homeassistant.helpers import selector


class ServiceResultEntitiesOptionsFlow(config_entries.OptionsFlow):
    """
    Handle options flow for the integration.

    This class manages the options that users can modify after initial setup,
    specifically the polling interval. Service configuration changes are
    handled via the Reconfigure flow.

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
        configure the polling interval.

        Args:
            user_input: The user input from the options form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an options entry.
        """
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL)},
            )

        current_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=10,
                        max=86400,
                        step=1,
                        unit_of_measurement="s",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )


__all__ = ["ServiceResultEntitiesOptionsFlow"]
