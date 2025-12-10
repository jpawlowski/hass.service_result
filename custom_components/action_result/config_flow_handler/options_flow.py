"""
Options flow for action_result.

This module implements the options flow that allows users to modify the
update mode and mode-specific settings after initial configuration.

Transformation settings (response data path, attribute name) and action
configuration changes should be done via the Reconfigure flow, not the
Options flow. This follows the Home Assistant pattern where data contains
core configuration and options contains adjustable settings.

For more information:
https://developers.home-assistant.io/docs/config_entries_options_flow_handler
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from custom_components.action_result.const import (
    CONF_SCAN_INTERVAL,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UPDATE_MODE,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
)
from homeassistant import config_entries
from homeassistant.helpers import selector


class ActionResultEntitiesOptionsFlow(config_entries.OptionsFlow):
    """
    Handle options flow for the integration.

    This class manages the options that users can modify after initial setup,
    specifically the update mode and mode-specific settings. Action and
    transformation configuration changes are handled via the Reconfigure flow.

    For more information:
    https://developers.home-assistant.io/docs/config_entries_options_flow_handler
    """

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """
        Initialize options flow.

        Args:
            config_entry: The config entry for this integration instance.

        Note:
            The config_entry parameter is automatically stored by the parent class.
            We don't need to explicitly assign it to self.config_entry as that's
            deprecated and will be removed in Home Assistant 2025.12.
        """
        self._options: dict[str, Any] = {}

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle options flow Step 1: Update mode selection.

        Args:
            user_input: The user input from the options form, or None for initial display.

        Returns:
            The config flow result, either showing a form or proceeding to mode-specific settings.
        """
        if user_input is not None:
            update_mode = user_input.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
            self._options[CONF_UPDATE_MODE] = update_mode

            # Route to the appropriate settings step based on mode
            if update_mode == UPDATE_MODE_POLLING:
                return await self.async_step_polling_settings()
            if update_mode == UPDATE_MODE_STATE_TRIGGER:
                return await self.async_step_state_trigger_settings()
            # Manual mode has no additional settings
            return await self.async_step_manual_settings()

        # Get current update mode from config entry data (not options)
        current_mode = self.config_entry.data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_MODE,
                    default=current_mode,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            {
                                "value": UPDATE_MODE_POLLING,
                                "label": "Polling (Regular Interval)",
                            },
                            {
                                "value": UPDATE_MODE_MANUAL,
                                "label": "Manual (update_entity service)",
                            },
                            {
                                "value": UPDATE_MODE_STATE_TRIGGER,
                                "label": "State Trigger (Entity State Change)",
                            },
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )

    async def async_step_polling_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle options flow Step 2: Polling mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an options entry.
        """
        if user_input is not None:
            self._options[CONF_SCAN_INTERVAL] = user_input.get(
                CONF_SCAN_INTERVAL,
                DEFAULT_SCAN_INTERVAL_SECONDS,
            )
            # Create options entry with all collected data
            return self.async_create_entry(title="", data=self._options)

        # Get current value from config entry data
        current_interval = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

        schema = vol.Schema(
            {
                vol.Required(
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
            step_id="polling_settings",
            data_schema=schema,
        )

    async def async_step_state_trigger_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle options flow Step 2: State trigger mode settings.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, either showing a form or creating an options entry.
        """
        if user_input is not None:
            self._options[CONF_TRIGGER_ENTITY] = user_input.get(CONF_TRIGGER_ENTITY, "")
            self._options[CONF_TRIGGER_FROM_STATE] = user_input.get(CONF_TRIGGER_FROM_STATE, "")
            self._options[CONF_TRIGGER_TO_STATE] = user_input.get(CONF_TRIGGER_TO_STATE, "")
            # Create options entry with all collected data
            return self.async_create_entry(title="", data=self._options)

        # Get current values from config entry data
        current_trigger_entity = self.config_entry.data.get(CONF_TRIGGER_ENTITY, "")
        current_from_state = self.config_entry.data.get(CONF_TRIGGER_FROM_STATE, "")
        current_to_state = self.config_entry.data.get(CONF_TRIGGER_TO_STATE, "")

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_TRIGGER_ENTITY,
                    default=current_trigger_entity,
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(),
                ),
                vol.Optional(
                    CONF_TRIGGER_FROM_STATE,
                    default=current_from_state,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Optional(
                    CONF_TRIGGER_TO_STATE,
                    default=current_to_state,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
            },
        )

        return self.async_show_form(
            step_id="state_trigger_settings",
            data_schema=schema,
        )

    async def async_step_manual_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """
        Handle options flow Step 2: Manual mode settings.

        Manual mode has no additional settings, so this step just creates
        the options entry immediately.

        Args:
            user_input: The user input from the form, or None for initial display.

        Returns:
            The config flow result, creating an options entry.
        """
        # Manual mode has no settings, just create the entry
        return self.async_create_entry(title="", data=self._options)


__all__ = ["ActionResultEntitiesOptionsFlow"]
