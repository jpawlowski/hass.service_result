"""
User flow steps for action_result config flow.

Contains steps for initial setup:
- async_step_user: Basic configuration (name, service action)
- async_step_device_selection: Parent device selection
- async_step_sensor_type: Data vs Value sensor selection
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import get_device_selection_schema, get_user_schema
from custom_components.action_result.config_flow_handler.steps.helpers import (
    extract_action_from_selector,
    validate_service_call,
)
from custom_components.action_result.const import CONF_NAME, CONF_PARENT_DEVICE, CONF_SERVICE_ACTION, LOGGER
from homeassistant.core import SupportsResponse
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_user(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 1: Basic configuration.

    User can:
    1. Enter a name for the sensor
    2. Select and configure a service action using the visual ActionSelector

    The ActionSelector in HA 2025.11+ includes a visual editor for service data
    with an integrated YAML view, so no separate YAML field is needed.

    Args:
        handler: The config flow handler instance.
        user_input: The user input from the config flow form, or None for initial display.

    Returns:
        The config flow result, either showing a form or proceeding to next step.
    """
    errors: dict[str, str] = {}
    description_placeholders: dict[str, str] = {}

    if user_input is not None:
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
            # Store data for next step
            name = user_input.get(CONF_NAME, f"{domain}.{service_name}")

            # Extract device_id from target if present
            device_id = target.get("device_id") if target else None

            handler._step_data = {  # noqa: SLF001
                CONF_NAME: name,
                CONF_SERVICE_ACTION: action_selector_data,
                "_service_domain": domain,  # Store for device filtering
                "_target_device_id": device_id,  # Store device from target
                "_response_variable": response_variable,  # Store for suggested attribute name
            }
            # Proceed to device selection
            from custom_components.action_result.config_flow_handler.steps.user_steps import (  # noqa: PLC0415
                async_step_device_selection,
            )

            return await async_step_device_selection(handler)

    return handler.async_show_form(
        step_id="user",
        data_schema=get_user_schema(user_input),
        errors=errors,
        description_placeholders=description_placeholders if description_placeholders else None,
    )


async def async_step_device_selection(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 1b: Parent device selection.

    Shows only devices from the integration that owns the service.
    If integration has no devices, proceeds to next step automatically.

    Used by both user flow and reconfigure flow.

    Args:
        handler: The config flow handler instance.
        user_input: The user input from the form, or None for initial display.

    Returns:
        The config flow result, proceeding to next step.
    """
    if user_input is not None:
        # Store parent device selection
        parent_device = user_input.get(CONF_PARENT_DEVICE)
        handler._step_data[CONF_PARENT_DEVICE] = parent_device if parent_device else ""  # noqa: SLF001

        # In user flow - proceed to sensor type selection
        return await async_step_sensor_type(handler)

    # Get integration domain from device if we have a target device
    integration_domain = None
    target_device_id = handler._step_data.get("_target_device_id")  # noqa: SLF001

    if target_device_id:
        # Get device registry to look up the integration
        device_registry = dr.async_get(handler.hass)
        device = device_registry.async_get(target_device_id)
        if device and device.identifiers:
            # Get integration domain from device identifiers
            # Device identifiers format: {(domain, unique_id), ...}
            for identifier in device.identifiers:
                if isinstance(identifier, tuple) and len(identifier) >= 1:
                    integration_domain = identifier[0]
                    break

    # Fallback to service domain if we couldn't determine from device
    if not integration_domain:
        integration_domain = handler._step_data.get("_service_domain")  # noqa: SLF001

    LOGGER.debug(
        "Showing device selection for integration '%s' (from device: %s)",
        integration_domain,
        target_device_id,
    )

    # For user flow only: handle defaults
    # User flow: Only set default if user already made a selection in this flow
    # This allows going back and forth while preserving the choice
    # But on first visit, the field is empty (user can choose to leave it empty)
    defaults = {}
    if CONF_PARENT_DEVICE in handler._step_data:  # noqa: SLF001
        parent_device = handler._step_data.get(CONF_PARENT_DEVICE, "")  # noqa: SLF001
        if parent_device:
            defaults[CONF_PARENT_DEVICE] = parent_device
            LOGGER.debug(
                "device_selection (user flow): Using parent device from current flow: %s",
                parent_device,
            )
        # Note: We do NOT use _target_device_id as default
        # This would prevent users from creating entities without a parent device

    # Show device selection form
    return handler.async_show_form(
        step_id="device_selection",
        data_schema=get_device_selection_schema(integration_domain, defaults),
    )


async def async_step_sensor_type(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 2: Sensor type selection.

    Choose between Data Sensor (response in attributes) or Value Sensor (value as state).

    Args:
        handler: The config flow handler instance.
        user_input: The user input from the form, or None for initial display.

    Returns:
        The config flow result, either showing a menu or proceeding to sensor-specific settings.
    """
    # Show menu for sensor type selection
    return handler.async_show_menu(
        step_id="sensor_type",
        menu_options=["data_sensor", "value_sensor"],
    )
