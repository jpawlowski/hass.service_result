"""
Data sensor configuration steps.

Contains:
- async_step_data_sensor: Data sensor selection from menu
- async_step_data_settings: Configure response data extraction
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import get_data_settings_schema
from custom_components.action_result.config_flow_handler.steps.helpers import clean_config_data
from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_SENSOR_TYPE,
    CONF_UPDATE_MODE,
    DEFAULT_ATTRIBUTE_NAME,
    LOGGER,
    SENSOR_TYPE_DATA,
)
from custom_components.action_result.utils import extract_data_at_path
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_data_sensor(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Data Sensor selection from menu."""
    handler._step_data[CONF_SENSOR_TYPE] = SENSOR_TYPE_DATA  # noqa: SLF001

    # Data sensors are always diagnostic (they contain metadata, not primary data)
    handler._step_data["entity_category"] = "diagnostic"  # noqa: SLF001

    return await async_step_data_settings(handler)


async def async_step_data_settings(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 3: Data sensor settings.

    Configure response data extraction for data sensors.
    Used by both user flow and reconfigure flow.

    Args:
        handler: The config flow handler instance.
        user_input: The user input from the form, or None for initial display.

    Returns:
        The config flow result, either showing a form or proceeding to next step.
    """
    errors: dict[str, str] = {}

    if user_input is not None:
        response_path = user_input.get(CONF_RESPONSE_DATA_PATH, "")

        # Validate the response path if provided
        if response_path:
            service_action = handler._step_data.get("service_action")  # noqa: SLF001
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
                if isinstance(handler._step_data.get("service_action"), dict):  # noqa: SLF001
                    service_data = handler._step_data["service_action"].get("data", {})  # noqa: SLF001
                    target_data = handler._step_data["service_action"].get("target", {})  # noqa: SLF001
                    target = target_data if target_data else None
                elif isinstance(handler._step_data.get("service_action"), list):  # noqa: SLF001
                    first_action = handler._step_data["service_action"][0]  # noqa: SLF001
                    service_data = first_action.get("data", {})
                    target_data = first_action.get("target", {})
                    target = target_data if target_data else None

                try:
                    # Call the service to get response
                    response = await handler.hass.services.async_call(
                        domain,
                        service_name,
                        service_data=service_data,
                        target=target,
                        blocking=True,
                        return_response=True,
                    )

                    # Try to extract the data at the specified path
                    extracted_data = extract_data_at_path(response, response_path)

                    if extracted_data is None:
                        errors["base"] = "invalid_response_path"
                except HomeAssistantError as ex:
                    LOGGER.debug("Error testing response path: %s", ex)
                    errors["base"] = "value_path_test_failed"

        if not errors:
            # Store data sensor settings
            handler._step_data[CONF_RESPONSE_DATA_PATH] = response_path  # noqa: SLF001
            handler._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)  # noqa: SLF001

            # Check if we're in reconfigure flow (has update_mode already set)
            is_reconfigure = CONF_UPDATE_MODE in handler._step_data and handler._step_data.get(CONF_UPDATE_MODE)  # noqa: SLF001

            if is_reconfigure:
                # Reconfigure flow - update entry and finish
                entry = handler._get_reconfigure_entry()  # noqa: SLF001
                # Clean config data: remove temporary fields and empty values
                cleaned_data = clean_config_data(handler._step_data)  # noqa: SLF001
                return handler.async_update_reload_and_abort(
                    entry,
                    data=cleaned_data,
                )

            # User flow - proceed to update mode selection
            from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
                async_step_update_mode,
            )

            return await async_step_update_mode(handler)

    return handler.async_show_form(
        step_id="data_settings",
        data_schema=get_data_settings_schema(handler._step_data),  # noqa: SLF001
        errors=errors,
    )
