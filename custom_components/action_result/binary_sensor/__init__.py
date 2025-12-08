"""Binary sensor platform for action_result.

This platform creates binary sensor entities for boolean values extracted
from service call responses.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

from custom_components.action_result.const import (
    CONF_ATTRIBUTE_NAME,
    CONF_DEVICE_CLASS,
    CONF_INCLUDE_RESPONSE_DATA,
    CONF_NAME,
    CONF_RESPONSE_DATA_PATH,
    CONF_RESPONSE_DATA_PATH_ATTRIBUTES,
    CONF_SERVICE_ACTION,
    DEFAULT_ATTRIBUTE_NAME,
    PARALLEL_UPDATES as PARALLEL_UPDATES,
)
from custom_components.action_result.entity import ActionResultEntitiesEntity
from custom_components.action_result.utils import convert_to_bool, extract_data_at_path
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

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
    """Set up the binary sensor platform."""
    async_add_entities(
        [
            ServiceResultBinarySensor(
                coordinator=entry.runtime_data.coordinator,
                entry=entry,
            )
        ]
    )


class ServiceResultBinarySensor(BinarySensorEntity, ActionResultEntitiesEntity):
    """Binary sensor entity that exposes boolean values from service responses.

    This sensor extracts a boolean value from the service response and exposes
    it as a binary sensor (on/off). The entity is unavailable when the service
    call fails or the extracted value cannot be converted to a boolean.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:api"

    def __init__(
        self,
        coordinator: ActionResultEntitiesDataUpdateCoordinator,
        entry: ActionResultEntitiesConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
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
        unrecorded = {"response_path", "last_update"}
        if entry.data.get(CONF_INCLUDE_RESPONSE_DATA, False):
            # Get the configured attribute name for response data
            attribute_name = entry.data.get(CONF_ATTRIBUTE_NAME, DEFAULT_ATTRIBUTE_NAME)
            unrecorded.add(attribute_name)
        self._attr_entity_component_unrecorded_attributes = frozenset(unrecorded)

        # Set device class if configured
        device_class = entry.data.get(CONF_DEVICE_CLASS)
        if device_class:
            with contextlib.suppress(ValueError):
                self._attr_device_class = BinarySensorDeviceClass(device_class)

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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.last_update_success:
            return None

        data = self.coordinator.data
        if not data or not data.get("success"):
            return None

        # Get the service response
        response = data.get("response")

        # Extract value at the specified path
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        extracted_value = extract_data_at_path(response, response_path)

        # Convert to boolean
        return convert_to_bool(extracted_value)

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

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Available only if coordinator succeeded and value is convertible
        if not self.coordinator.last_update_success:
            return False

        data = self.coordinator.data
        if not data or not data.get("success"):
            return False

        # Check if value can be converted to boolean
        response = data.get("response")
        response_path = self._entry.data.get(CONF_RESPONSE_DATA_PATH, "")
        extracted_value = extract_data_at_path(response, response_path)

        return convert_to_bool(extracted_value) is not None
