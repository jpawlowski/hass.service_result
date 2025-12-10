"""
Config flow schemas.

Schemas for the main configuration flow steps:
- User setup (configure service to call) - multi-step
- Reconfiguration - multi-step

The flow is organized in steps:
1. Basic configuration (Name, Service Action)
2. Transformation (Response Data Path, Attribute Name)
3. Update mode selection
4. Mode-specific settings
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEFINE_ENUM,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_CATEGORY,
    CONF_ENUM_ICONS,
    CONF_ENUM_TRANSLATION_LANGUAGES,
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
    CONF_UNIT_DENOMINATOR,
    CONF_UNIT_NUMERATOR,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_UPDATE_MODE,
    CONF_VALUE_TYPE,
    DEFAULT_ATTRIBUTE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_SENSOR_TYPE,
    DEFAULT_UPDATE_MODE,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
    UNIT_CUSTOM_COMPOSITE,
    UPDATE_MODE_MANUAL,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_STRING,
    VALUE_TYPE_TIMESTAMP,
)
from custom_components.action_result.helpers import (
    get_all_sensor_device_classes,
    get_all_units_of_measurement,
    get_base_units_of_measurement,
)
from homeassistant import data_entry_flow
from homeassistant.helpers import selector

_LOGGER = logging.getLogger(__name__)


def get_transformation_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for transformation step (Step 2: Data transformation settings).

    This step configures how the service response data is extracted and exposed.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for transformation configuration.
    """
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Optional(
                CONF_RESPONSE_DATA_PATH,
                default=defaults.get(CONF_RESPONSE_DATA_PATH, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=False,
                ),
            ),
            vol.Optional(
                CONF_ATTRIBUTE_NAME,
                default=defaults.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
        },
    )


# Section key for advanced options (deprecated - kept for backwards compatibility)
SECTION_ADVANCED_OPTIONS = "advanced_options"


def _get_advanced_options_schema(defaults: Mapping[str, Any] | None = None) -> data_entry_flow.section:
    """
    Get the schema for the advanced options section.

    This helper function creates the collapsible advanced options section
    that is shared across all mode-specific settings steps.

    Args:
        defaults: Optional dictionary of default values. Can contain either
                  flat keys (CONF_RESPONSE_DATA_PATH) or nested under
                  SECTION_ADVANCED_OPTIONS.

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
            },
        ),
        {"collapsed": True},
    )


def get_device_selection_schema(
    integration_domain: str | None = None, defaults: Mapping[str, Any] | None = None
) -> vol.Schema:
    """
    Get schema for parent device selection (Step 1b: Device Selection).

    Shows only devices from the integration that owns the service.
    If integration has no devices, this step can be skipped.

    Args:
        integration_domain: The domain of the integration (extracted from service).
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for device selection.
    """
    defaults = defaults or {}

    # Build device selector filtered by integration domain
    if integration_domain:
        device_selector = selector.DeviceSelector(
            selector.DeviceSelectorConfig(
                integration=integration_domain,
            )
        )
    else:
        device_selector = selector.DeviceSelector()

    return vol.Schema(
        {
            vol.Optional(
                CONF_PARENT_DEVICE,
                default=defaults.get(CONF_PARENT_DEVICE, vol.UNDEFINED),
            ): device_selector,
        },
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


def get_sensor_type_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for sensor type selection (Step 2: Sensor Type).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for sensor type selection.
    """
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_SENSOR_TYPE,
                default=defaults.get(CONF_SENSOR_TYPE, DEFAULT_SENSOR_TYPE),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=SENSOR_TYPE_DATA, label="Data Sensor"),
                        selector.SelectOptionDict(value=SENSOR_TYPE_VALUE, label="Value Sensor"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="sensor_type",
                ),
            ),
        },
    )


def get_value_path_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for value sensor path configuration (Step 3a: Value Path).

    This is the first step for value sensors where the user specifies the paths
    for extracting the value and optionally for the attributes.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for value sensor path configuration.
    """
    defaults = defaults or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_RESPONSE_DATA_PATH,
                default=defaults.get(CONF_RESPONSE_DATA_PATH, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=False,
                ),
            ),
            vol.Optional(
                CONF_RESPONSE_DATA_PATH_ATTRIBUTES,
                default=defaults.get(CONF_RESPONSE_DATA_PATH_ATTRIBUTES, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=False,
                ),
            ),
            vol.Optional(
                CONF_INCLUDE_RESPONSE_DATA,
                default=defaults.get(CONF_INCLUDE_RESPONSE_DATA, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ATTRIBUTE_NAME,
                default=defaults.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
        },
    )


def get_value_configuration_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for value sensor configuration (Step 3b: Value Configuration).

    This is the second step for value sensors where the user configures
    value type, unit, and device class. Auto-detected suggestions are
    provided as defaults.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for value sensor configuration.
    """
    defaults = defaults or {}

    # Get all available units and device classes
    available_units = get_all_units_of_measurement()
    available_device_classes = get_all_sensor_device_classes()

    return vol.Schema(
        {
            vol.Optional(
                CONF_VALUE_TYPE,
                default=defaults.get(CONF_VALUE_TYPE, VALUE_TYPE_STRING),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=VALUE_TYPE_STRING, label="Text"),
                        selector.SelectOptionDict(value=VALUE_TYPE_NUMBER, label="Number"),
                        selector.SelectOptionDict(value=VALUE_TYPE_BOOLEAN, label="Boolean (On/Off)"),
                        selector.SelectOptionDict(value=VALUE_TYPE_TIMESTAMP, label="Timestamp"),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="value_type",
                ),
            ),
            vol.Optional(
                CONF_UNIT_OF_MEASUREMENT,
                default=defaults.get(CONF_UNIT_OF_MEASUREMENT, ""),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value="", label="None")]
                    + [selector.SelectOptionDict(value=UNIT_CUSTOM_COMPOSITE, label="Custom Composite Unit")]
                    + [selector.SelectOptionDict(value=unit, label=unit) for unit in available_units],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,  # Allow custom units not in the list
                ),
            ),
            vol.Optional(
                CONF_DEVICE_CLASS,
                default=defaults.get(CONF_DEVICE_CLASS, ""),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value="", label="None")]
                    + [
                        selector.SelectOptionDict(value=dc, label=dc.replace("_", " ").title())
                        for dc in available_device_classes
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Optional(
                CONF_ICON,
                default=defaults.get(CONF_ICON, ""),
            ): selector.IconSelector(),
            vol.Optional(
                CONF_ENTITY_CATEGORY,
                # Use 'or vol.UNDEFINED' to treat empty strings as UNDEFINED (no default)
                default=defaults.get(CONF_ENTITY_CATEGORY, vol.UNDEFINED) or vol.UNDEFINED,
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["diagnostic"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="entity_category",
                ),
            ),
        },
    )


def get_composite_unit_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for custom composite unit builder (Step 3c: Composite Unit).

    This step allows the user to build a custom composite unit by selecting
    a numerator and denominator from base units.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for composite unit configuration.
    """
    defaults = defaults or {}

    # Get base units (no composites)
    base_units = get_base_units_of_measurement()

    return vol.Schema(
        {
            vol.Required(
                CONF_UNIT_NUMERATOR,
                default=defaults.get(CONF_UNIT_NUMERATOR, ""),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=unit, label=unit) for unit in base_units],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,  # Allow custom numerator
                ),
            ),
            vol.Required(
                CONF_UNIT_DENOMINATOR,
                default=defaults.get(CONF_UNIT_DENOMINATOR, ""),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=unit, label=unit) for unit in base_units],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,  # Allow custom denominator
                ),
            ),
        },
    )


def get_enum_definition_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for enum definition (Step: Enum Definition).

    This step is shown after value_configuration when value_type is "string".
    User can choose to define enum values for their text sensor.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for enum definition.
    """
    defaults = defaults or {}

    # Get current value if available to prefill
    enum_values_default = defaults.get(CONF_ENUM_VALUES, "")

    # If current value is provided, include it in the default
    current_value = defaults.get("_current_value")
    if current_value and enum_values_default:
        # Ensure current value is in the list
        values_list = [v.strip() for v in str(enum_values_default).split(",") if v.strip()]
        if current_value not in values_list:
            values_list.insert(0, current_value)
            enum_values_default = ", ".join(values_list)
    elif current_value and not enum_values_default:
        # Only current value - use it as default
        enum_values_default = current_value

    return vol.Schema(
        {
            vol.Optional(
                CONF_DEFINE_ENUM,
                default=defaults.get(CONF_DEFINE_ENUM, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ENUM_VALUES,
                default=enum_values_default,
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=True,
                ),
            ),
        },
    )


def get_enum_icons_schema(enum_values: list[str], defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for enum icon mapping (Step: Enum Icons).

    This step allows user to assign an icon to each enum value.
    Shown only if CONF_DEFINE_ENUM is True.

    Args:
        enum_values: List of enum values to create icon selectors for.
        defaults: Optional dictionary of default values (existing enum_icons).

    Returns:
        Voluptuous schema for enum icon configuration.
    """
    defaults = defaults or {}
    existing_icons = defaults.get(CONF_ENUM_ICONS, {})

    schema_dict = {}
    for value in enum_values:
        schema_dict[vol.Optional(value, default=existing_icons.get(value, ""))] = selector.IconSelector()

    return vol.Schema(schema_dict)


def get_enum_translation_languages_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for selecting which languages to translate enum values into.

    English is always included. User can select additional languages.

    Args:
        defaults: Optional dictionary of default values.

    Returns:
        Voluptuous schema for language selection.
    """
    defaults = defaults or {}

    # List of common Home Assistant languages
    # English is mandatory and will be added automatically
    available_languages = [
        selector.SelectOptionDict(value="de", label="German (Deutsch)"),
        selector.SelectOptionDict(value="fr", label="French (Français)"),
        selector.SelectOptionDict(value="es", label="Spanish (Español)"),
        selector.SelectOptionDict(value="it", label="Italian (Italiano)"),
        selector.SelectOptionDict(value="nl", label="Dutch (Nederlands)"),
        selector.SelectOptionDict(value="pl", label="Polish (Polski)"),
        selector.SelectOptionDict(value="pt", label="Portuguese (Português)"),
        selector.SelectOptionDict(value="ru", label="Russian (Русский)"),
        selector.SelectOptionDict(value="sv", label="Swedish (Svenska)"),
        selector.SelectOptionDict(value="da", label="Danish (Dansk)"),
        selector.SelectOptionDict(value="nb", label="Norwegian (Norsk)"),
        selector.SelectOptionDict(value="fi", label="Finnish (Suomi)"),
        selector.SelectOptionDict(value="cs", label="Czech (Čeština)"),
        selector.SelectOptionDict(value="sk", label="Slovak (Slovenčina)"),
        selector.SelectOptionDict(value="hu", label="Hungarian (Magyar)"),
        selector.SelectOptionDict(value="ro", label="Romanian (Română)"),
        selector.SelectOptionDict(value="bg", label="Bulgarian (Български)"),
        selector.SelectOptionDict(value="hr", label="Croatian (Hrvatski)"),
        selector.SelectOptionDict(value="sl", label="Slovenian (Slovenščina)"),
        selector.SelectOptionDict(value="el", label="Greek (Ελληνικά)"),
    ]

    return vol.Schema(
        {
            vol.Optional(
                CONF_ENUM_TRANSLATION_LANGUAGES,
                default=defaults.get(CONF_ENUM_TRANSLATION_LANGUAGES, []),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=available_languages,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                ),
            ),
        },
    )


def get_enum_translation_schema(
    language: str, enum_values: list[str], defaults: Mapping[str, Any] | None = None
) -> vol.Schema:
    """
    Get schema for translating enum values into a specific language.

    This step is dynamically generated for each selected language.

    Args:
        language: Language code (e.g., "en", "de", "fr").
        enum_values: List of enum values to translate.
        defaults: Optional dictionary of default values (existing translations for this language).

    Returns:
        Voluptuous schema for enum translations.
    """
    defaults = defaults or {}
    existing_translations = defaults.get(CONF_ENUM_TRANSLATIONS, {}).get(language, {})

    schema_dict = {}
    for value in enum_values:
        schema_dict[vol.Required(value, default=existing_translations.get(value, value))] = selector.TextSelector(
            selector.TextSelectorConfig(
                type=selector.TextSelectorType.TEXT,
            ),
        )

    return vol.Schema(schema_dict)


def get_value_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for value sensor configuration (Step 3: Value Settings).

    DEPRECATED: Use get_value_path_schema() and get_value_configuration_schema() instead.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for value sensor settings.
    """
    # Deprecated - keeping for backwards compatibility during development
    return get_value_configuration_schema(defaults)


def get_data_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for data sensor configuration (Step 3: Data Settings).

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Voluptuous schema for data sensor settings.
    """
    defaults = defaults or {}

    # Use response_variable as suggested value for attribute name if available
    response_var = defaults.get("_response_variable")
    attribute_name_default = defaults.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

    _LOGGER.debug(
        "get_data_settings_schema: response_var=%s, attribute_name_default=%s, all_defaults=%s",
        response_var,
        attribute_name_default,
        defaults,
    )

    # Build attribute name field configuration
    attribute_name_config: dict[str, Any] = {
        "default": attribute_name_default,
    }
    if response_var:
        # Use suggested_value to pre-fill the field (user can clear it)
        attribute_name_config["description"] = {"suggested_value": response_var}
        _LOGGER.debug("Using response_variable '%s' as suggested_value", response_var)

    return vol.Schema(
        {
            vol.Optional(
                CONF_RESPONSE_DATA_PATH,
                default=defaults.get(CONF_RESPONSE_DATA_PATH, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=False,
                ),
            ),
            vol.Optional(
                CONF_ATTRIBUTE_NAME,
                **attribute_name_config,
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
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
                        selector.SelectOptionDict(value=UPDATE_MODE_POLLING, label="Polling (Regular Interval)"),
                        selector.SelectOptionDict(value=UPDATE_MODE_MANUAL, label="Manual (update_entity service)"),
                        selector.SelectOptionDict(
                            value=UPDATE_MODE_STATE_TRIGGER, label="State Trigger (Entity State Change)"
                        ),
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="update_mode",
                ),
            ),
        },
    )


def get_polling_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for polling mode settings (Step 4 - Polling mode).

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
        },
    )


def get_state_trigger_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for state trigger mode settings (Step 4 - State Trigger mode).

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
                # Use 'or vol.UNDEFINED' to treat empty strings as UNDEFINED (no default)
                default=defaults.get(CONF_TRIGGER_ENTITY, vol.UNDEFINED) or vol.UNDEFINED,
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
        },
    )


def get_manual_settings_schema(defaults: Mapping[str, Any] | None = None) -> vol.Schema:
    """
    Get schema for manual mode settings (Step 4 - Manual mode).

    Manual mode has no specific settings.

    Args:
        defaults: Optional dictionary of default values to pre-populate the form.

    Returns:
        Empty voluptuous schema (manual mode needs no additional configuration).
    """
    return vol.Schema({})


def get_reconfigure_schema(current_data: Mapping[str, Any], integration_domain: str | None = None) -> vol.Schema:
    """
    Get schema for reconfigure step (Step 1: Action configuration).

    Note: The name field is not included here because renaming should be done
    through Home Assistant's built-in entity renaming mechanism after initial setup.
    The integration uses the config entry's entry_id as a stable unique identifier.

    In Home Assistant 2025.11+, the ActionSelector includes a visual editor for service data
    with an integrated YAML view.

    Args:
        current_data: Current configuration data to pre-fill in the form.
        integration_domain: Optional integration domain for device filtering.

    Returns:
        Voluptuous schema for reconfiguration.
    """
    _LOGGER.debug(
        "get_reconfigure_schema: integration_domain=%s, current_data keys=%s",
        integration_domain,
        list(current_data.keys()),
    )
    # Build action default from domain/name if present
    service_action = current_data.get(CONF_SERVICE_ACTION, {})
    if not service_action:
        # Backwards compatibility: build from old format
        domain = current_data.get("service_domain", "")
        name = current_data.get("service_name", "")
        if domain and name:
            service_action = {"action": f"{domain}.{name}"}

    # Build device selector with optional integration filter
    if integration_domain:
        config = selector.DeviceSelectorConfig(
            integration=integration_domain,
        )
        _LOGGER.debug("Creating DeviceSelector with config: integration=%s", integration_domain)
        device_selector = selector.DeviceSelector(config)
        _LOGGER.debug("DeviceSelector created: %s", device_selector)
    else:
        _LOGGER.debug("Creating DeviceSelector without integration filter")
        device_selector = selector.DeviceSelector()

    schema = vol.Schema(
        {
            vol.Optional(
                CONF_SERVICE_ACTION,
                default=service_action if service_action else vol.UNDEFINED,
            ): selector.ActionSelector(),
        },
    )

    _LOGGER.debug("Reconfigure schema: service_action only")
    return schema


__all__ = [
    "SECTION_ADVANCED_OPTIONS",
    "get_composite_unit_schema",
    "get_data_settings_schema",
    "get_manual_settings_schema",
    "get_polling_settings_schema",
    "get_reconfigure_schema",
    "get_sensor_type_schema",
    "get_state_trigger_settings_schema",
    "get_transformation_schema",
    "get_update_mode_schema",
    "get_user_schema",
    "get_value_configuration_schema",
    "get_value_path_schema",
    "get_value_settings_schema",  # Deprecated
]
