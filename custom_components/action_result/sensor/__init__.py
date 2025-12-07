"""Sensor platform for action_result.

This platform creates a single sensor entity per config entry that exposes
the response data from the configured Home Assistant service call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_SERVICE_ACTION,
    DEFAULT_ATTRIBUTE_NAME,
    ERROR_TYPE_PERMANENT,
    ERROR_TYPE_TEMPORARY,
    PARALLEL_UPDATES as PARALLEL_UPDATES,
    STATE_ERROR,
    STATE_OK,
    STATE_RETRYING,
    STATE_UNAVAILABLE,
)
from custom_components.action_result.entity import ActionResultEntitiesEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

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
    async_add_entities(
        [
            ServiceResultSensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
            )
        ]
    )


class ServiceResultSensor(SensorEntity, ActionResultEntitiesEntity):
    """Sensor entity that exposes service response data.

    The main purpose of this sensor is to expose the full service response
    in a configurable attribute. The state reflects the current status:
    - ok: Last service call was successful
    - error: Last service call failed with a permanent error
    - retrying: Last service call failed, will retry automatically
    - unavailable: Service is unavailable (e.g., integration not loaded)
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
        name = entry.data.get(CONF_NAME, "Service Result")
        self._attr_name = name

        # Set translation key for proper naming
        self._attr_translation_key = "action_result"

    def _get_service_action(self) -> str:
        """Get the service action name from config (e.g., 'domain.service')."""
        service_action = self._entry.data.get(CONF_SERVICE_ACTION)
        if service_action and isinstance(service_action, dict):
            return service_action.get("action", "unknown")
        return "unknown"

    def _extract_data_at_path(self, data: Any, path: str | None) -> Any:
        """
        Extract data from a nested structure using a dot-notation path.

        Supports both positive and negative indices for list access.
        Negative indices access elements from the end (e.g., -1 for last element).

        Args:
            data: The data structure to traverse.
            path: A dot-separated path (e.g., "results.0.values" or "data.items").
                  Can use negative indices like "items.-1" for last element.

        Returns:
            The data at the specified path, or the original data if path is empty/None.
        """
        if path is None or not path.strip():
            return data

        current = data
        for key in path.strip().split("."):
            if current is None:
                return None

            # Handle list indices (supports negative indices)
            if isinstance(current, list):
                try:
                    index = int(key)
                    # Validate index bounds (handles both positive and negative)
                    if -len(current) <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    # Key is not a valid index for a list
                    return None
            elif isinstance(current, dict):
                current = current.get(key)
            else:
                # Cannot traverse further
                return None

        return current

    @property
    def native_value(self) -> str:
        """Return the state of the sensor.

        Returns different states based on the service call result:
        - 'ok': Successful service call
        - 'retrying': Temporary error, will retry
        - 'error': Permanent error, needs user attention
        - 'unavailable': Service unavailable
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
        attributes["service"] = self._get_service_action()

        # Get configuration for data extraction
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        attribute_name = self._entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)

        if self.coordinator.data:
            # Get the service response
            response = self.coordinator.data.get("response")

            # Extract data at the specified path (if configured)
            extracted_data = self._extract_data_at_path(response, response_path)

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
