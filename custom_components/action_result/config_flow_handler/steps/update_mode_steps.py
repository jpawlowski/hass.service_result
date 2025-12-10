"""
Update mode selection and mode-specific settings steps.

Contains:
- async_step_update_mode: Menu for update mode selection
- async_step_polling_mode, async_step_state_trigger_mode, async_step_manual_mode: Mode selections
- async_step_polling_settings, async_step_state_trigger_settings, async_step_manual_settings: Settings

This module was split from config_flow.py for better maintainability (originally 400+ lines).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import (
    get_manual_settings_schema,
    get_polling_settings_schema,
    get_state_trigger_settings_schema,
)
from custom_components.action_result.config_flow_handler.steps.helpers import clean_config_data
from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEFINE_ENUM,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENUM_ICONS,
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
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_MODE,
    CONF_VALUE_TYPE,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
)

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_update_mode(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Step 2: Update mode selection."""
    # Show menu for update mode selection
    return handler.async_show_menu(
        step_id="update_mode",
        menu_options=["polling_mode", "state_trigger_mode", "manual_mode"],
    )


async def async_step_polling_mode(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Polling mode selection from menu."""
    handler._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_POLLING  # noqa: SLF001
    return await async_step_polling_settings(handler)


async def async_step_state_trigger_mode(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle State Trigger mode selection from menu."""
    handler._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_STATE_TRIGGER  # noqa: SLF001
    return await async_step_state_trigger_settings(handler)


async def async_step_manual_mode(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Manual mode selection from menu."""
    handler._step_data[CONF_UPDATE_MODE] = UPDATE_MODE_MANUAL  # noqa: SLF001
    return await async_step_manual_settings(handler)


def _build_entry_data(handler: ActionResultEntitiesConfigFlowHandler, user_input: dict[str, Any]) -> dict[str, Any]:
    """
    Build entry data from step_data and user_input.

    Common helper used by all mode settings steps.
    """
    sensor_type = handler._step_data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)  # noqa: SLF001
    update_mode = handler._step_data.get(CONF_UPDATE_MODE, UPDATE_MODE_POLLING)  # noqa: SLF001

    entry_data: dict[str, Any] = {
        CONF_NAME: handler._step_data[CONF_NAME],  # noqa: SLF001
        CONF_SERVICE_ACTION: handler._step_data[CONF_SERVICE_ACTION],  # noqa: SLF001
        CONF_SENSOR_TYPE: sensor_type,
        CONF_UPDATE_MODE: update_mode,
        CONF_PARENT_DEVICE: handler._step_data.get(CONF_PARENT_DEVICE, ""),  # noqa: SLF001
        CONF_ENTITY_CATEGORY: handler._step_data.get(CONF_ENTITY_CATEGORY, ""),  # noqa: SLF001
    }

    # Mode-specific fields
    if update_mode == UPDATE_MODE_POLLING:
        entry_data[CONF_SCAN_INTERVAL] = user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
        entry_data[CONF_TRIGGER_ENTITY] = ""
        entry_data[CONF_TRIGGER_FROM_STATE] = ""
        entry_data[CONF_TRIGGER_TO_STATE] = ""
    elif update_mode == UPDATE_MODE_STATE_TRIGGER:
        entry_data[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL_SECONDS
        entry_data[CONF_TRIGGER_ENTITY] = user_input.get(CONF_TRIGGER_ENTITY, "")
        entry_data[CONF_TRIGGER_FROM_STATE] = user_input.get(CONF_TRIGGER_FROM_STATE, "")
        entry_data[CONF_TRIGGER_TO_STATE] = user_input.get(CONF_TRIGGER_TO_STATE, "")
    else:  # MANUAL
        entry_data[CONF_SCAN_INTERVAL] = DEFAULT_SCAN_INTERVAL_SECONDS
        entry_data[CONF_TRIGGER_ENTITY] = ""
        entry_data[CONF_TRIGGER_FROM_STATE] = ""
        entry_data[CONF_TRIGGER_TO_STATE] = ""

    # Sensor-type specific fields
    if sensor_type == SENSOR_TYPE_VALUE:
        entry_data[CONF_RESPONSE_DATA_PATH] = handler._step_data.get(CONF_RESPONSE_DATA_PATH, "")  # noqa: SLF001
        entry_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = handler._step_data.get(  # noqa: SLF001
            CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
        )
        entry_data[CONF_VALUE_TYPE] = handler._step_data.get(CONF_VALUE_TYPE, "")  # noqa: SLF001
        entry_data[CONF_UNIT_OF_MEASUREMENT] = handler._step_data.get(CONF_UNIT_OF_MEASUREMENT, "")  # noqa: SLF001
        entry_data[CONF_DEVICE_CLASS] = handler._step_data.get(CONF_DEVICE_CLASS, "")  # noqa: SLF001
        entry_data[CONF_ICON] = handler._step_data.get(CONF_ICON, "")  # noqa: SLF001
        entry_data[CONF_INCLUDE_RESPONSE_DATA] = handler._step_data.get(CONF_INCLUDE_RESPONSE_DATA, False)  # noqa: SLF001
        # Only include attribute_name if include_response_data is enabled
        if entry_data[CONF_INCLUDE_RESPONSE_DATA]:
            entry_data[CONF_ATTRIBUTE_NAME] = handler._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)  # noqa: SLF001
        # Add enum data if defined
        if handler._step_data.get(CONF_DEFINE_ENUM, False):  # noqa: SLF001
            entry_data[CONF_DEFINE_ENUM] = True
            entry_data[CONF_ENUM_VALUES] = handler._step_data.get(CONF_ENUM_VALUES, [])  # noqa: SLF001
            entry_data[CONF_ENUM_ICONS] = handler._step_data.get(CONF_ENUM_ICONS, {})  # noqa: SLF001
            entry_data[CONF_ENUM_TRANSLATIONS] = handler._step_data.get(CONF_ENUM_TRANSLATIONS, {})  # noqa: SLF001
    else:  # Data sensor
        entry_data[CONF_RESPONSE_DATA_PATH] = handler._step_data.get(CONF_RESPONSE_DATA_PATH, "")  # noqa: SLF001
        entry_data[CONF_ATTRIBUTE_NAME] = handler._step_data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)  # noqa: SLF001

    return entry_data


async def async_step_polling_settings(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Step 3: Polling mode settings."""
    if user_input is not None:
        entry_data = _build_entry_data(handler, user_input)
        return handler.async_create_entry(
            title=handler._step_data[CONF_NAME],  # noqa: SLF001
            data=entry_data,
        )

    return handler.async_show_form(
        step_id="polling_settings",
        data_schema=get_polling_settings_schema(handler._step_data),  # noqa: SLF001
    )


async def async_step_state_trigger_settings(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Step 3: State trigger mode settings."""
    if user_input is not None:
        entry_data = _build_entry_data(handler, user_input)
        # Clean config data: remove empty values to allow defaults
        cleaned_data = clean_config_data(entry_data)
        return handler.async_create_entry(
            title=handler._step_data[CONF_NAME],  # noqa: SLF001
            data=cleaned_data,
        )

    return handler.async_show_form(
        step_id="state_trigger_settings",
        data_schema=get_state_trigger_settings_schema(handler._step_data),  # noqa: SLF001
    )


async def async_step_manual_settings(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Step 3: Manual mode settings."""
    if user_input is not None:
        entry_data = _build_entry_data(handler, user_input)
        # Clean config data: remove empty values to allow defaults
        cleaned_data = clean_config_data(entry_data)
        return handler.async_create_entry(
            title=handler._step_data[CONF_NAME],  # noqa: SLF001
            data=cleaned_data,
        )

    return handler.async_show_form(
        step_id="manual_settings",
        data_schema=get_manual_settings_schema(handler._step_data),  # noqa: SLF001
    )
