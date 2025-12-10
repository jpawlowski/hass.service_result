"""
Config flow for action_result.

This module implements the main configuration flow including:
- Initial user setup (service configuration) - multi-step
- Reconfiguration of existing entries - multi-step

The config flow is organized in steps:
1. Basic configuration (Name, Service Action)
2. Update mode selection (Polling, Manual, State Trigger)
3. Mode-specific settings with collapsible advanced options

Step implementations are modularized in the steps/ package for better maintainability.

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from typing import Any

from custom_components.action_result.const import DOMAIN, LOGGER
from homeassistant import config_entries
from homeassistant.helpers import device_registry as dr, entity_registry as er


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

    def _update_entity_device_association(
        self,
        entry: config_entries.ConfigEntry,
        new_parent_device_id: str | None,
    ) -> None:
        """
        Update entity's device association when parent device changes.

        When the parent device is changed or removed, we need to update
        the entity registry to reflect the new device association.

        If parent device is removed, entities will be associated with our own
        virtual device (which will be created on reload).

        If parent device is set, we need to clean up our old virtual device if it exists.

        Args:
            entry: The config entry being updated.
            new_parent_device_id: New parent device ID, or None/empty to remove association.
        """
        # Get registries
        entity_reg = er.async_get(self.hass)
        device_reg = dr.async_get(self.hass)

        # Find our own virtual device (if it exists)
        own_device = device_reg.async_get_device(identifiers={(entry.domain, entry.entry_id)})

        # Find all entities for this config entry
        entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

        if new_parent_device_id:
            # Setting a parent device - associate entities with it
            parent_device = device_reg.async_get(new_parent_device_id)
            if parent_device:
                LOGGER.debug(
                    "Associating entities with parent device: %s (%s)",
                    parent_device.name,
                    new_parent_device_id,
                )

                # Update each entity to use parent device
                for entity_entry in entities:
                    entity_reg.async_update_entity(
                        entity_entry.entity_id,
                        device_id=parent_device.id,
                    )
                    LOGGER.debug(
                        "Updated entity %s to use parent device %s",
                        entity_entry.entity_id,
                        parent_device.id,
                    )

                # Clean up our own virtual device if it exists and has no other entities
                if own_device:
                    # Check if device has any other entities (from other config entries)
                    device_entities = er.async_entries_for_device(
                        entity_reg, own_device.id, include_disabled_entities=True
                    )
                    # Filter to entities NOT from this config entry
                    other_entities = [e for e in device_entities if e.config_entry_id != entry.entry_id]

                    if not other_entities:
                        # No other entities - safe to remove device
                        device_reg.async_remove_device(own_device.id)
                        LOGGER.debug(
                            "Removed empty virtual device: %s (%s)",
                            own_device.name,
                            own_device.id,
                        )
        else:
            # Removing parent device - entities will use our own virtual device
            # The virtual device will be created on reload by the entity's __init__
            # We just need to clear the device association so entities can create it
            LOGGER.debug("Clearing parent device association - entities will use virtual device on reload")

            # Remove device association from entities
            # They will be re-associated with our virtual device on reload
            for entity_entry in entities:
                entity_reg.async_update_entity(
                    entity_entry.entity_id,
                    device_id=None,  # Clear device - will be set on reload
                )
                LOGGER.debug(
                    "Cleared device association for entity %s (will use virtual device on reload)",
                    entity_entry.entity_id,
                )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """
        Get the options flow for this handler.

        Returns:
            The options flow instance for modifying integration options.
        """
        from custom_components.action_result.config_flow_handler.options_flow import (  # noqa: PLC0415
            ActionResultEntitiesOptionsFlow,
        )

        return ActionResultEntitiesOptionsFlow(config_entry)

    # ====================================
    # Step delegation to modular functions
    # ====================================

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 1: Basic configuration."""
        from custom_components.action_result.config_flow_handler.steps.user_steps import (  # noqa: PLC0415
            async_step_user,
        )

        return await async_step_user(self, user_input)

    async def async_step_device_selection(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 1b: Parent device selection."""
        from custom_components.action_result.config_flow_handler.steps.user_steps import (  # noqa: PLC0415
            async_step_device_selection,
        )

        return await async_step_device_selection(self, user_input)

    async def async_step_sensor_type(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 2: Sensor type selection."""
        from custom_components.action_result.config_flow_handler.steps.user_steps import (  # noqa: PLC0415
            async_step_sensor_type,
        )

        return await async_step_sensor_type(self, user_input)

    async def async_step_data_sensor(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Data Sensor selection from menu."""
        from custom_components.action_result.config_flow_handler.steps.data_steps import (  # noqa: PLC0415
            async_step_data_sensor,
        )

        return await async_step_data_sensor(self, user_input)

    async def async_step_value_sensor(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Value Sensor selection from menu."""
        from custom_components.action_result.config_flow_handler.steps.value_steps import (  # noqa: PLC0415
            async_step_value_sensor,
        )

        return await async_step_value_sensor(self, user_input)

    async def async_step_data_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3: Data sensor settings."""
        from custom_components.action_result.config_flow_handler.steps.data_steps import (  # noqa: PLC0415
            async_step_data_settings,
        )

        return await async_step_data_settings(self, user_input)

    async def async_step_value_path(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3a: Value sensor path configuration."""
        from custom_components.action_result.config_flow_handler.steps.value_steps import (  # noqa: PLC0415
            async_step_value_path,
        )

        return await async_step_value_path(self, user_input)

    async def async_step_value_configuration(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3b: Value sensor configuration."""
        from custom_components.action_result.config_flow_handler.steps.value_steps import (  # noqa: PLC0415
            async_step_value_configuration,
        )

        return await async_step_value_configuration(self, user_input)

    async def async_step_composite_unit(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3c: Build custom composite unit."""
        from custom_components.action_result.config_flow_handler.steps.value_steps import (  # noqa: PLC0415
            async_step_composite_unit,
        )

        return await async_step_composite_unit(self, user_input)

    async def async_step_enum_definition(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Enum Definition step."""
        from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
            async_step_enum_definition,
        )

        return await async_step_enum_definition(self, user_input)

    async def async_step_enum_icons(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Enum Icons step."""
        from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
            async_step_enum_icons,
        )

        return await async_step_enum_icons(self, user_input)

    async def async_step_enum_translation_languages(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Enum Translation Languages selection step."""
        from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
            async_step_enum_translation_languages,
        )

        return await async_step_enum_translation_languages(self, user_input)

    async def async_step_enum_translation(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Enum Translation step for a specific language."""
        from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
            async_step_enum_translation,
        )

        return await async_step_enum_translation(self, user_input)

    async def async_step_update_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 2: Update mode selection."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_update_mode,
        )

        return await async_step_update_mode(self, user_input)

    async def async_step_polling_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Polling mode selection from menu."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_polling_mode,
        )

        return await async_step_polling_mode(self, user_input)

    async def async_step_state_trigger_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle State Trigger mode selection from menu."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_state_trigger_mode,
        )

        return await async_step_state_trigger_mode(self, user_input)

    async def async_step_manual_mode(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Manual mode selection from menu."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_manual_mode,
        )

        return await async_step_manual_mode(self, user_input)

    async def async_step_polling_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3: Polling mode settings."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_polling_settings,
        )

        return await async_step_polling_settings(self, user_input)

    async def async_step_state_trigger_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3: State trigger mode settings."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_state_trigger_settings,
        )

        return await async_step_state_trigger_settings(self, user_input)

    async def async_step_manual_settings(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle Step 3: Manual mode settings."""
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_manual_settings,
        )

        return await async_step_manual_settings(self, user_input)

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration Step 1: Basic configuration."""
        from custom_components.action_result.config_flow_handler.steps.reconfigure_steps import (  # noqa: PLC0415
            async_step_reconfigure,
        )

        return await async_step_reconfigure(self, user_input)


__all__ = ["ActionResultEntitiesConfigFlowHandler"]
