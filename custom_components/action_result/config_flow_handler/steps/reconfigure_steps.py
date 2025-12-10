"""
Reconfigure flow step.

Contains the reconfigure step that allows updating existing config entries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import get_reconfigure_schema
from custom_components.action_result.config_flow_handler.steps.helpers import (
    extract_action_from_selector,
    validate_service_call,
)
from custom_components.action_result.const import (
    CONF_NAME,
    CONF_SENSOR_TYPE,
    CONF_SERVICE_ACTION,
    LOGGER,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
)
from homeassistant.core import SupportsResponse

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_reconfigure(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle reconfiguration Step 1: Basic configuration (reusing user flow logic).

    Allows users to update the service configuration without removing
    and re-adding the integration. This step reuses the same logic as
    async_step_user but pre-fills with existing entry data.
    """
    entry = handler._get_reconfigure_entry()  # noqa: SLF001
    errors: dict[str, str] = {}
    description_placeholders: dict[str, str] = {}

    if user_input is not None:
        # Initialize step_data with existing entry data if not already set
        if not handler._step_data:  # noqa: SLF001
            handler._step_data = dict(entry.data)  # noqa: SLF001

        action_selector_data = user_input.get(CONF_SERVICE_ACTION)

        # Extract domain and service from the ActionSelector
        domain: str | None = None
        service_name: str | None = None
        response_variable: str | None = None

        if action_selector_data:
            try:
                extracted = extract_action_from_selector(action_selector_data)
                if extracted:
                    domain, service_name = extracted
            except ValueError:
                # Multiple actions selected - not supported
                errors["base"] = "multiple_actions_not_supported"

        if not errors:
            if not domain or not service_name:
                errors["base"] = "no_service_selected"
            elif not handler.hass.services.has_service(domain, service_name):
                errors["base"] = "service_not_found"
        if not errors and domain and service_name:
            # Check if service supports returning response data
            supports_response = handler.hass.services.supports_response(domain, service_name)
            if supports_response == SupportsResponse.NONE:
                errors["base"] = "service_no_response"
                description_placeholders["service_name"] = f"{domain}.{service_name}"
            else:
                # Get service data, target, and response_variable from the ActionSelector
                service_data = {}
                target = None
                if isinstance(action_selector_data, dict):
                    service_data = action_selector_data.get("data", {})
                    # Only set target if it has actual data
                    target_data = action_selector_data.get("target", {})
                    target = target_data if target_data else None
                    # Extract response_variable if present
                    response_variable = action_selector_data.get("response_variable")
                elif isinstance(action_selector_data, list) and action_selector_data:
                    service_data = action_selector_data[0].get("data", {})
                    # Only set target if it has actual data
                    target_data = action_selector_data[0].get("target", {})
                    target = target_data if target_data else None
                    # Extract response_variable if present
                    response_variable = action_selector_data[0].get("response_variable")

                # Debug logging
                LOGGER.debug(
                    "Validating service %s.%s with data=%s, target=%s",
                    domain,
                    service_name,
                    service_data,
                    target,
                )

                # Actually call the service to validate it works
                success, error_key, error_msg = await validate_service_call(
                    handler.hass, domain, service_name, service_data, target
                )
                if not success and error_key:
                    errors["base"] = error_key
                    if error_msg:
                        description_placeholders["error_message"] = error_msg

        if not errors:
            # Extract device_id from target if present
            device_id = target.get("device_id") if target else None

            # Initialize step_data from entry data if not already done
            if not handler._step_data:  # noqa: SLF001
                handler._step_data = dict(entry.data)  # noqa: SLF001

            # Update step_data with new values from user input
            handler._step_data[CONF_SERVICE_ACTION] = action_selector_data  # noqa: SLF001
            handler._step_data["_service_domain"] = domain  # Store for device filtering  # noqa: SLF001
            handler._step_data["_target_device_id"] = device_id  # Store device from target  # noqa: SLF001
            handler._step_data["_response_variable"] = (  # noqa: SLF001
                response_variable  # Store for suggested attribute name
            )
            # Keep name from existing entry (name changes should use HA's built-in rename)
            handler._step_data[CONF_NAME] = entry.data.get(CONF_NAME, f"{domain}.{service_name}")  # noqa: SLF001

            # Reconfigure flow: Skip device selection, go directly to sensor-specific settings
            # Parent device is set during initial setup and cannot be changed
            sensor_type = handler._step_data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)  # noqa: SLF001
            if sensor_type == SENSOR_TYPE_VALUE:
                from custom_components.action_result.config_flow_handler.steps.value_steps import (  # noqa: PLC0415
                    async_step_value_path,
                )

                return await async_step_value_path(handler)

            from custom_components.action_result.config_flow_handler.steps.data_steps import (  # noqa: PLC0415
                async_step_data_settings,
            )

            return await async_step_data_settings(handler)

    # Initialize step_data from entry data for display
    if not handler._step_data:  # noqa: SLF001
        handler._step_data = dict(entry.data)  # noqa: SLF001

    return handler.async_show_form(
        step_id="reconfigure",
        data_schema=get_reconfigure_schema(handler._step_data),  # noqa: SLF001
        errors=errors,
        description_placeholders=description_placeholders if description_placeholders else None,
    )
