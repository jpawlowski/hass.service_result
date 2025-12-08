"""Sensor platform for action_result.

This platform creates sensor entities that expose response data from
configured Home Assistant service calls. Supports two sensor types:

1. Data Sensor: Exposes response data in attributes with status as state
2. Value Sensor: Extracts a value from response and uses it as state
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.validators import convert_value_to_type
from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEFINE_ENUM,
    CONF_DEVICE_CLASS,
    CONF_ENUM_ICONS,
    CONF_ENUM_TRANSLATIONS,
    CONF_ENUM_VALUES,
    CONF_ICON,
    CONF_INCLUDE_RESPONSE_DATA,
    CONF_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_RESPONSE_DATA_PATH_ATTRIBUTES,
    CONF_SENSOR_TYPE,
    CONF_SERVICE_ACTION,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TYPE,
    DEFAULT_ATTRIBUTE_NAME,
    ERROR_TYPE_PERMANENT,
    ERROR_TYPE_TEMPORARY,
    PARALLEL_UPDATES as PARALLEL_UPDATES,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
    STATE_ERROR,
    STATE_OK,
    STATE_RETRYING,
    STATE_UNAVAILABLE,
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_TIMESTAMP,
)
from custom_components.action_result.entity import ActionResultEntitiesEntity
from custom_components.action_result.utils import extract_data_at_path
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.action_result.coordinator import ActionResultEntitiesDataUpdateCoordinator
    from custom_components.action_result.data import ActionResultEntitiesConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActionResultEntitiesConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)

    # Create appropriate sensor type
    if sensor_type == SENSOR_TYPE_VALUE:
        sensor = ServiceResultValueSensor(
            coordinator=entry.runtime_data.coordinator,
            entry=entry,
        )
    else:  # Data sensor
        sensor = ServiceResultDataSensor(
            coordinator=entry.runtime_data.coordinator,
            entry=entry,
        )

    async_add_entities([sensor])


class ServiceResultDataSensor(SensorEntity, ActionResultEntitiesEntity, RestoreEntity):
    """Data sensor that exposes service response data in attributes.

    This sensor type keeps the response data in attributes and uses the state
    to indicate the status of the service call (ok, error, retrying, unavailable).
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:api"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_OK, STATE_ERROR, STATE_RETRYING, STATE_UNAVAILABLE]

    def __init__(
        self,
        coordinator: ActionResultEntitiesDataUpdateCoordinator,
        entry: ActionResultEntitiesConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Set unique ID from config entry
        self._attr_unique_id = f"{entry.entry_id}_action_result"

        # Get name from config
        name = entry.data.get(CONF_NAME, "Action Result")
        self._attr_name = name

        # Set translation key for proper naming
        self._attr_translation_key = "action_result"

        # Set unrecorded attributes (must be set in __init__ since attribute_name is dynamic)
        attribute_name = entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
        self._attr_entity_component_unrecorded_attributes = frozenset({attribute_name, "response_path", "last_update"})

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant.

        Restores the last known state to provide continuity across restarts.
        This is particularly important for manual update mode where updates
        might not happen immediately after startup.
        """
        await super().async_added_to_hass()

        # Restore last state if available
        if (last_state := await self.async_get_last_state()) is not None:
            # Restore native_value (state)
            if self._attr_options and last_state.state in self._attr_options:
                self._attr_native_value = last_state.state

    def _get_service_action(self) -> str:
        """Get the service action name from config (e.g., 'domain.service')."""
        service_action = self._entry.data.get(CONF_SERVICE_ACTION)
        if service_action:
            # Handle list format (sequence of actions) - take first action
            if isinstance(service_action, list):
                if service_action:
                    service_action = service_action[0]
                else:
                    return "unknown"

            # Handle dict format (single action)
            if isinstance(service_action, dict):
                return service_action.get("action", "unknown")
        return "unknown"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor.

        Returns different states based on the service call result:
        - 'ok': Successful service call
        - 'retrying': Temporary error, will retry
        - 'error': Permanent error, needs user attention
        - 'unavailable': Action unavailable
        """
        if not self.coordinator.last_update_success:
            # Determine if we're retrying or permanently failed
            if self.coordinator.is_retrying:
                return STATE_RETRYING
            if self.coordinator.last_error_type == ERROR_TYPE_PERMANENT:
                return STATE_ERROR
            if self.coordinator.last_error_type == ERROR_TYPE_TEMPORARY:
                return STATE_RETRYING
            return STATE_UNAVAILABLE

        data = self.coordinator.data
        if data and data.get("success"):
            return STATE_OK

        return STATE_ERROR

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        The data attribute (with configurable name) contains the service response,
        optionally extracted from a specific path in the response structure.
        """
        attributes: dict[str, Any] = {}

        # Get service action name
        attributes["action"] = self._get_service_action()

        # Get configuration for data extraction
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        attribute_name = self._entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

        if self.coordinator.data:
            # Get the service response
            response = self.coordinator.data.get("response")

            # Extract data at the specified path (if configured)
            extracted_data = extract_data_at_path(response, response_path)

            # Use the configured attribute name
            attributes[attribute_name] = extracted_data

            # Add metadata
            attributes["last_update"] = self.coordinator.data.get("last_update")
            attributes["success"] = self.coordinator.data.get("success", False)

            # Include path info if configured
            if response_path:
                attributes["response_path"] = response_path

            if self.coordinator.data.get("error"):
                attributes["error_message"] = self.coordinator.data.get("error")
        else:
            attributes[attribute_name] = None
            attributes["success"] = False
            # Include path info for consistency even when data is None
            if response_path:
                attributes["response_path"] = response_path

        # Include error information from coordinator
        if self.coordinator.last_error:
            attributes["error_message"] = self.coordinator.last_error
            attributes["error_type"] = self.coordinator.last_error_type

        # Include retry information if relevant
        if self.coordinator.consecutive_errors > 0:
            attributes["consecutive_errors"] = self.coordinator.consecutive_errors
            if self.coordinator.is_retrying:
                attributes["retry_delay_seconds"] = self.coordinator.get_retry_delay()

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available.

        The entity is always available to show error states.
        """
        return True


class ServiceResultValueSensor(SensorEntity, ActionResultEntitiesEntity, RestoreEntity):
    """Value sensor that extracts a value from service response and uses it as state.

    This sensor type extracts a specific value from the response and displays it
    as the sensor's state. Optionally includes the full response in attributes.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:api"

    def __init__(
        self,
        coordinator: ActionResultEntitiesDataUpdateCoordinator,
        entry: ActionResultEntitiesConfigEntry,
    ) -> None:
        """Initialize the value sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Set unique ID from config entry
        self._attr_unique_id = f"{entry.entry_id}_action_result"

        # Get name from config
        name = entry.data.get(CONF_NAME, "Action Result")
        self._attr_name = name

        # Set translation key for proper naming
        self._attr_translation_key = "action_result"

        # Set unrecorded attributes dynamically based on configuration
        # Always exclude response_path and last_update from recorder (metadata)
        # Also exclude response data attribute if user enabled it (can contain large data)
        # Also exclude translations attribute if enum is defined (can contain large multilingual data)
        unrecorded = {"response_path", "last_update"}
        if entry.data.get(CONF_INCLUDE_RESPONSE_DATA, False):
            # Get the configured attribute name for response data
            attribute_name = entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            unrecorded.add(attribute_name)
        if entry.data.get(CONF_DEFINE_ENUM, False):
            # Enum translations can be large (multiple languages × multiple values)
            unrecorded.add("translations")
        self._attr_entity_component_unrecorded_attributes = frozenset(unrecorded)

        # Set unit of measurement if configured
        unit = entry.data.get(CONF_UNIT_OF_MEASUREMENT, "")
        if unit:
            self._attr_native_unit_of_measurement = unit

        # Set device class if configured
        device_class = entry.data.get(CONF_DEVICE_CLASS, "")
        if device_class:
            with contextlib.suppress(ValueError):
                self._attr_device_class = SensorDeviceClass(device_class)

        # Set state class for numeric values
        value_type = entry.data.get(CONF_VALUE_TYPE, "")
        if value_type == VALUE_TYPE_NUMBER:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif value_type == VALUE_TYPE_TIMESTAMP:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

        # Set enum options if defined
        if entry.data.get(CONF_DEFINE_ENUM, False):
            enum_values = entry.data.get(CONF_ENUM_VALUES, [])
            if enum_values:
                self._attr_options = enum_values
                # REQUIRED: Set device class to ENUM when options are provided
                self._attr_device_class = SensorDeviceClass.ENUM
                # Set translation key for enum state translations
                self._attr_translation_key = "action_result_enum"

    @property
    def icon(self) -> str | None:
        """Return icon based on enum state, configuration, or default.

        Priority:
        1. Enum state icon (if enum defined and state matches)
        2. Custom configured icon
        3. Default icon "mdi:api"
        """
        # Check for enum-based icon first
        if self._entry.data.get(CONF_DEFINE_ENUM, False):
            enum_icons = self._entry.data.get(CONF_ENUM_ICONS, {})
            if self.native_value and self.native_value in enum_icons:
                enum_icon = enum_icons.get(self.native_value)
                if enum_icon:
                    return enum_icon

        # Fall back to custom configured icon
        custom_icon = self._entry.data.get(CONF_ICON, "")
        if custom_icon:
            return custom_icon

        # Final fallback to default
        return self._attr_icon

    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant.

        Restores the last known state and attributes to provide continuity
        across restarts. This ensures the sensor displays the last known value
        until a new update is received from the coordinator.
        """
        await super().async_added_to_hass()

        # Restore last state if available
        if (last_state := await self.async_get_last_state()) is not None:
            # Restore native_value (state) - handle None for unavailable state
            if last_state.state not in ("unknown", "unavailable"):
                # For timestamp sensors, parse the string back to datetime
                value_type = self._entry.data.get(CONF_VALUE_TYPE, "")
                if value_type == VALUE_TYPE_TIMESTAMP:
                    parsed_dt = dt_util.parse_datetime(last_state.state)
                    if parsed_dt:
                        self._attr_native_value = parsed_dt
                    else:
                        # If parsing fails, skip restoration
                        pass
                else:
                    self._attr_native_value = last_state.state

    def _get_service_action(self) -> str:
        """Get the service action name from config (e.g., 'domain.service')."""
        service_action = self._entry.data.get(CONF_SERVICE_ACTION)
        if service_action:
            # Handle list format (sequence of actions) - take first action
            if isinstance(service_action, list):
                if service_action:
                    service_action = service_action[0]
                else:
                    return "unknown"

            # Handle dict format (single action)
            if isinstance(service_action, dict):
                return service_action.get("action", "unknown")
        return "unknown"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor (extracted value)."""
        if not self.coordinator.last_update_success:
            return None

        data = self.coordinator.data
        if not data or not data.get("success"):
            return None

        # Get the service response
        response = data.get("response")

        # Extract value at the specified path
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        value = extract_data_at_path(response, response_path)

        if value is None:
            return None

        # Convert value to the configured value type
        value_type = self._entry.data.get(CONF_VALUE_TYPE, "")
        if value_type:
            converted_value = convert_value_to_type(value, value_type)
            if converted_value is None:
                self.coordinator.logger.warning(
                    "Failed to convert value '%s' to type '%s' for sensor %s",
                    value,
                    value_type,
                    self.entity_id,
                )
            return converted_value

        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attributes: dict[str, Any] = {}

        # Get service action name
        attributes["action"] = self._get_service_action()

        # Include response path
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        if response_path:
            attributes["response_path"] = response_path

        # Include response data if configured (using separate attributes path if set)
        include_response = self._entry.data.get(CONF_INCLUDE_RESPONSE_DATA, False)
        if include_response and self.coordinator.data:
            response = self.coordinator.data.get("response")
            # Use separate attributes path if configured, otherwise full response (empty path)
            attributes_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH_ATTRIBUTES, "")
            extracted_data = extract_data_at_path(response, attributes_path)
            # Use configured attribute name (default: "data")
            attribute_name = self._entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            attributes[attribute_name] = extracted_data

        # Add metadata
        if self.coordinator.data:
            attributes["last_update"] = self.coordinator.data.get("last_update")
            attributes["success"] = self.coordinator.data.get("success", False)

            if self.coordinator.data.get("error"):
                attributes["error_message"] = self.coordinator.data.get("error")
        else:
            attributes["success"] = False

        # Include error information from coordinator
        if self.coordinator.last_error:
            attributes["error_message"] = self.coordinator.last_error
            attributes["error_type"] = self.coordinator.last_error_type

        # Include retry information if relevant
        if self.coordinator.consecutive_errors > 0:
            attributes["consecutive_errors"] = self.coordinator.consecutive_errors
            if self.coordinator.is_retrying:
                attributes["retry_delay_seconds"] = self.coordinator.get_retry_delay()

        # Include enum translations if defined
        if self._entry.data.get(CONF_DEFINE_ENUM, False):
            enum_translations = self._entry.data.get(CONF_ENUM_TRANSLATIONS, {})
            if enum_translations:
                # Add translations for current state if available
                current_value = self.native_value
                if current_value:
                    translated_values = {}
                    for lang, translations in enum_translations.items():
                        if current_value in translations:
                            translated_values[lang] = translations[current_value]
                    if translated_values:
                        attributes["translations"] = translated_values

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Available only if coordinator succeeded
        if not self.coordinator.last_update_success:
            return False

        data = self.coordinator.data
        return bool(data and data.get("success"))
