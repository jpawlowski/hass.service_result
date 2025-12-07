"""
Config flow schemas.

Schemas for the main configuration flow steps:
- User setup (configure service to call) - multi-step
- Reconfiguration - multi-step

The flow is organized in steps:
1. Basic configuration (Name, Service Action)
2. Update mode selection
3. Mode-specific settings + advanced options
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_ACTION,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UPDATE_MODE,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
)
from homeassistant import data_entry_flow
from homeassistant.helpers import selector

# Section key for advanced options (response data path, attribute name)
SECTION_ADVANCED_OPTIONS = "advanced_options"


def _get_advanced_options_schema(defaults: Mapping[str, Any] | None = None) -> data_entry_flow.section:
    """
    Get the schema for the advanced options section.

    This helper function creates the collapsible advanced options section
    that is shared across all mode-specific settings steps.

    Args:
        defaults: Optional dictionary of default values. Can contain either
                  flat keys (CONF_RESPONSE_DATA_PATH, CONF_ATTRIBUTE_NAME)
                  or nested under SECTION_ADVANCED_OPTIONS.

    Returns:
        A data entry flow section containing the advanced options schema.
    """
    defaults = defaults or {}

    # Support both flat and nested defaults
    advanced_defaults = defaults.get(SECTION_ADVANCED_OPTIONS, {})
    response_path_default = advanced_defaults.get(
        CONF_RESPONSE_DATA_PATH,
        defaults.get(CONF_RESPONSE_DATA_PATH, ""),
    )
    attribute_name_default = advanced_defaults.get(
        CONF_ATTRIBUTE_NAME,
        defaults.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
    )

    return data_entry_flow.section(
        vol.Schema(
            {
                vol.Optional(
                    CONF_RESPONSE_DATA_PATH,
                    default=response_path_default,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Optional(
                    CONF_ATTRIBUTE_NAME,
                    default=attribute_name_default,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
            },
        ),
        {"collapsed": True},
    )


def get_user_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for user step (initial setup - Step 1: Basic configuration).

    The schema uses a service action selector for easy service selection and configuration.
    In Home Assistant 2025.11+, the ActionSelector includes a visual editor for service data
    with an integrated YAML view.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for service configuration input.
    """
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=defaults.get(CONF_NAME, vol.UNDEFINED),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Optional(
                CONF_SERVICE_ACTION,
                default=defaults.get(CONF_SERVICE_ACTION, vol.UNDEFINED),
            ): selector.ActionSelector(),
        },
    )


def get_update_mode_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for update mode selection step (Step 2).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for update mode selection.
    """
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_UPDATE_MODE,
                default=defaults.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=UPDATE_MODE_POLLING, label="Polling (cyclic)"),
                        selector.SelectOptionDict(value=UPDATE_MODE_MANUAL, label="Manual (update_entity)"),
                        selector.SelectOptionDict(value=UPDATE_MODE_STATE_TRIGGER, label="Entity State Trigger"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="update_mode",
                ),
            ),
        },
    )


def get_polling_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for polling mode settings (Step 3 - Polling mode).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for polling settings.
    """
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=10,
                    max=86400,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="seconds",
                ),
            ),
            vol.Optional(SECTION_ADVANCED_OPTIONS): _get_advanced_options_schema(defaults),
        },
    )


def get_state_trigger_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for state trigger mode settings (Step 3 - State Trigger mode).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for state trigger settings.
    """
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Optional(
                CONF_TRIGGER_ENTITY,
                default=defaults.get(CONF_TRIGGER_ENTITY, vol.UNDEFINED),
            ): selector.EntitySelector(),
            vol.Optional(
                CONF_TRIGGER_FROM_STATE,
                default=defaults.get(CONF_TRIGGER_FROM_STATE, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Optional(
                CONF_TRIGGER_TO_STATE,
                default=defaults.get(CONF_TRIGGER_TO_STATE, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Optional(SECTION_ADVANCED_OPTIONS): _get_advanced_options_schema(defaults),
        },
    )


def get_manual_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for manual mode settings (Step 3 - Manual mode).

    Manual mode has no interval or trigger settings, only advanced options.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for manual mode settings.
    """
    return vol.Schema(
        {
            vol.Optional(SECTION_ADVANCED_OPTIONS): _get_advanced_options_schema(defaults),
        },
    )


def get_reconfigure_schema(current_data: Mapping[str, Any]) -> vol.Schema:
    """
    Get schema for reconfigure step (Step 1: Service configuration).

    Note: The name field is not included here because renaming should be done
    through Home Assistant's built-in entity renaming mechanism after initial setup.
    The integration uses the config entry's entry_id as a stable unique identifier.

    In Home Assistant 2025.11+, the ActionSelector includes a visual editor for service data
    with an integrated YAML view.

    Args:
        current_data: Current configuration data to pre-fill in the form.

    Returns:
        Voluptuous schema for reconfiguration.
    """
    # Build action default from domain/name if present
    service_action = current_data.get(CONF_SERVICE_ACTION, {})
    if not service_action:
        # Backwards compatibility: build from old format
        domain = current_data.get("service_domain", "")
        name = current_data.get("service_name", "")
        if domain and name:
            service_action = {"action": f"{domain}.{name}"}

    return vol.Schema(
        {
            vol.Optional(
                CONF_SERVICE_ACTION,
                default=service_action if service_action else vol.UNDEFINED,
            ): selector.ActionSelector(),
        },
    )


__all__ = [
    "SECTION_ADVANCED_OPTIONS",
    "get_manual_settings_schema",
    "get_polling_settings_schema",
    "get_reconfigure_schema",
    "get_state_trigger_settings_schema",
    "get_update_mode_schema",
    "get_user_schema",
]
