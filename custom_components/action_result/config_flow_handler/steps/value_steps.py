"""
Value sensor configuration steps.

Contains all steps related to value sensor configuration:
- async_step_value_sensor: Value sensor selection from menu
- async_step_value_path: Configure value extraction path
- async_step_value_configuration: Configure value type, unit, device class
- async_step_composite_unit: Build custom composite units
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import (
    get_composite_unit_schema,
    get_value_configuration_schema,
    get_value_path_schema,
)
from custom_components.action_result.config_flow_handler.steps.helpers import clean_config_data
from custom_components.action_result.config_flow_handler.validators import validate_value_type
from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ICON,
    CONF_INCLUDE_RESPONSE_DATA,
    CONF_RESPONSE_DATA_PATH,
    CONF_RESPONSE_DATA_PATH_ATTRIBUTES,
    CONF_SENSOR_TYPE,
    CONF_SERVICE_ACTION,
    CONF_UNIT_DENOMINATOR,
    CONF_UNIT_NUMERATOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_MODE,
    CONF_VALUE_TYPE,
    DEFAULT_ATTRIBUTE_NAME,
    LOGGER,
    SENSOR_TYPE_VALUE,
    UNIT_CUSTOM_COMPOSITE,
    VALUE_TYPE_STRING,
)
from custom_components.action_result.helpers import detect_value_type_and_suggestions
from custom_components.action_result.utils import extract_data_at_path
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_value_sensor(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """Handle Value Sensor selection from menu."""
    handler._step_data[CONF_SENSOR_TYPE] = SENSOR_TYPE_VALUE  # noqa: SLF001
    return await async_step_value_path(handler)


async def async_step_value_path(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 3a: Value sensor path configuration.

    User specifies the path to extract the value and optionally
    a different path for attributes.

    Used by both user flow and reconfigure flow.
    """
    errors: dict[str, str] = {}

    if user_input is not None:
        response_path = user_input.get(CONF_RESPONSE_DATA_PATH, "")

        # Validate that the path exists by calling the service (only if path is provided)
        if response_path:
            service_action = handler._step_data.get(CONF_SERVICE_ACTION)  # noqa: SLF001
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
                if isinstance(handler._step_data.get(CONF_SERVICE_ACTION), dict):  # noqa: SLF001
                    service_data = handler._step_data[CONF_SERVICE_ACTION].get("data", {})  # noqa: SLF001
                    target_data = handler._step_data[CONF_SERVICE_ACTION].get("target", {})  # noqa: SLF001
                    target = target_data if target_data else None
                elif isinstance(handler._step_data.get(CONF_SERVICE_ACTION), list):  # noqa: SLF001
                    first_action = handler._step_data[CONF_SERVICE_ACTION][0]  # noqa: SLF001
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

                    # Try to extract the value at the specified path
                    extracted_value = extract_data_at_path(response, response_path)

                    if extracted_value is None:
                        errors["base"] = "invalid_response_path"
                    elif isinstance(extracted_value, (dict, list)):
                        # Value sensor requires a leaf node (primitive value), not a structure
                        errors["base"] = "value_path_not_leaf"
                    else:
                        # Store the extracted value for auto-detection in next step
                        handler._step_data["_detected_value"] = extracted_value  # noqa: SLF001
                except HomeAssistantError as ex:
                    LOGGER.debug("Error testing value path: %s", ex)
                    errors["base"] = "value_path_test_failed"

        if not errors:
            # Store path settings
            handler._step_data[CONF_RESPONSE_DATA_PATH] = response_path  # noqa: SLF001
            handler._step_data[CONF_RESPONSE_DATA_PATH_ATTRIBUTES] = user_input.get(  # noqa: SLF001
                CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""
            )
            handler._step_data[CONF_INCLUDE_RESPONSE_DATA] = user_input.get(CONF_INCLUDE_RESPONSE_DATA, False)  # noqa: SLF001
            # Only store attribute_name if include_response_data is enabled
            if handler._step_data[CONF_INCLUDE_RESPONSE_DATA]:  # noqa: SLF001
                handler._step_data[CONF_ATTRIBUTE_NAME] = user_input.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)  # noqa: SLF001

            # Proceed to value configuration with auto-detection
            return await async_step_value_configuration(handler)

    return handler.async_show_form(
        step_id="value_path",
        data_schema=get_value_path_schema(handler._step_data),  # noqa: SLF001
        errors=errors,
    )


async def async_step_value_configuration(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 3b: Value sensor configuration.

    Configure value type, unit, and device class with auto-detected suggestions.
    Used by both user flow and reconfigure flow.
    """
    errors: dict[str, str] = {}

    if user_input is not None:
        # Validate that the detected value can be converted to the selected value type
        detected_value = handler._step_data.get("_detected_value")  # noqa: SLF001
        selected_value_type = user_input.get(CONF_VALUE_TYPE, "")

        if detected_value is not None and selected_value_type:
            is_valid, error_key, _ = validate_value_type(detected_value, selected_value_type)
            if not is_valid:
                errors["base"] = error_key or "value_type_mismatch"

        if not errors:
            # Check if user selected custom composite unit
            selected_unit = user_input.get(CONF_UNIT_OF_MEASUREMENT, "")
            if selected_unit == UNIT_CUSTOM_COMPOSITE:
                # Store value type and device class, but not the unit marker
                handler._step_data[CONF_VALUE_TYPE] = user_input.get(CONF_VALUE_TYPE, "")  # noqa: SLF001
                handler._step_data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS, "")  # noqa: SLF001
                # Route to composite unit builder
                return await async_step_composite_unit(handler)

            # Store value sensor configuration
            handler._step_data[CONF_VALUE_TYPE] = user_input.get(CONF_VALUE_TYPE, "")  # noqa: SLF001
            handler._step_data[CONF_UNIT_OF_MEASUREMENT] = selected_unit  # noqa: SLF001
            handler._step_data[CONF_DEVICE_CLASS] = user_input.get(CONF_DEVICE_CLASS, "")  # noqa: SLF001
            handler._step_data[CONF_ICON] = user_input.get(CONF_ICON, "")  # noqa: SLF001
            # Handle entity_category: None (cleared) should become empty string
            entity_category = user_input.get(CONF_ENTITY_CATEGORY)
            handler._step_data[CONF_ENTITY_CATEGORY] = entity_category if entity_category is not None else ""  # noqa: SLF001

            # Check if we're in reconfigure flow
            is_reconfigure = CONF_UPDATE_MODE in handler._step_data and handler._step_data.get(CONF_UPDATE_MODE)  # noqa: SLF001

            # Check if value_type is string - offer enum definition
            if user_input.get(CONF_VALUE_TYPE, "") == VALUE_TYPE_STRING:
                from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
                    async_step_enum_definition,
                )

                return await async_step_enum_definition(handler)

            # Not a string type
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

    # Auto-detect value type and suggestions from extracted value
    detected_value = handler._step_data.get("_detected_value")  # noqa: SLF001
    if detected_value is not None:
        suggestions = detect_value_type_and_suggestions(detected_value)
        # Pre-populate with suggestions if not already set
        if CONF_VALUE_TYPE not in handler._step_data:  # noqa: SLF001
            handler._step_data[CONF_VALUE_TYPE] = suggestions["value_type"]  # noqa: SLF001
        if CONF_UNIT_OF_MEASUREMENT not in handler._step_data:  # noqa: SLF001
            handler._step_data[CONF_UNIT_OF_MEASUREMENT] = suggestions["unit_of_measurement"]  # noqa: SLF001
        if CONF_DEVICE_CLASS not in handler._step_data:  # noqa: SLF001
            handler._step_data[CONF_DEVICE_CLASS] = suggestions["device_class"]  # noqa: SLF001

    return handler.async_show_form(
        step_id="value_configuration",
        data_schema=get_value_configuration_schema(handler._step_data),  # noqa: SLF001
        errors=errors,
    )


async def async_step_composite_unit(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Step 3c: Build custom composite unit.

    Allow user to build a composite unit from numerator and denominator.
    Used by both user flow and reconfigure flow.
    """
    if user_input is not None:
        # Build composite unit string from numerator and denominator
        numerator = user_input.get(CONF_UNIT_NUMERATOR, "")
        denominator = user_input.get(CONF_UNIT_DENOMINATOR, "")

        # Build the final composite unit (e.g., "€/kWh")
        composite_unit = f"{numerator}/{denominator}"
        handler._step_data[CONF_UNIT_OF_MEASUREMENT] = composite_unit  # noqa: SLF001

        # Check if we're in reconfigure flow
        is_reconfigure = CONF_UPDATE_MODE in handler._step_data and handler._step_data.get(CONF_UPDATE_MODE)  # noqa: SLF001

        # Check if value_type is string - offer enum definition
        if handler._step_data.get(CONF_VALUE_TYPE, "") == VALUE_TYPE_STRING:  # noqa: SLF001
            from custom_components.action_result.config_flow_handler.steps.enum_steps import (  # noqa: PLC0415
                async_step_enum_definition,
            )

            return await async_step_enum_definition(handler)

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
        step_id="composite_unit",
        data_schema=get_composite_unit_schema(),
    )
