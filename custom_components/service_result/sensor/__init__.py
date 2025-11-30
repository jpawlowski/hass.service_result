"""Sensor platform for service_result.

This platform creates a single sensor entity per config entry that exposes
the response data from the configured Home Assistant service call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.service_result.const import (
    CONF_NAME,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    PARALLEL_UPDATES as PARALLEL_UPDATES,
    STATE_ERROR,
    STATE_OK,
)
from custom_components.service_result.entity import ServiceResultEntitiesEntity
from homeassistant.components.sensor import SensorEntity

if TYPE_CHECKING:
    from custom_components.service_result.coordinator import ServiceResultEntitiesDataUpdateCoordinator
    from custom_components.service_result.data import ServiceResultEntitiesConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ServiceResultEntitiesConfigEntry,
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


class ServiceResultSensor(SensorEntity, ServiceResultEntitiesEntity):
    """Sensor entity that exposes service response data.

    The main purpose of this sensor is to expose the full service response
    in the `data` attribute. The state is a simple status indicator (ok/error).
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:api"

    def __init__(
        self,
        coordinator: ServiceResultEntitiesDataUpdateCoordinator,
        entry: ServiceResultEntitiesConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

        # Set unique ID from config entry
        self._attr_unique_id = f"{entry.entry_id}_service_result"

        # Get name from config
        name = entry.data.get(CONF_NAME, "Service Result")
        self._attr_name = name

        # Set translation key for proper naming
        self._attr_translation_key = "service_result"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor.

        Returns 'ok' if the last service call was successful, 'error' otherwise.
        """
        if not self.coordinator.last_update_success:
            return STATE_ERROR

        data = self.coordinator.data
        if data and data.get("success"):
            return STATE_OK

        return STATE_ERROR

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes.

        The 'data' attribute contains the full service response.
        """
        attributes: dict[str, Any] = {}

        # Get service info
        service_domain = self._entry.data.get(CONF_SERVICE_DOMAIN, "")
        service_name = self._entry.data.get(CONF_SERVICE_NAME, "")
        attributes["service"] = f"{service_domain}.{service_name}"

        if self.coordinator.data:
            # The main data attribute contains the service response
            response = self.coordinator.data.get("response")
            attributes["data"] = response

            # Add metadata
            attributes["last_update"] = self.coordinator.data.get("last_update")
            attributes["success"] = self.coordinator.data.get("success", False)

            if self.coordinator.data.get("error"):
                attributes["error_message"] = self.coordinator.data.get("error")
        else:
            attributes["data"] = None
            attributes["success"] = False

        # Include error from coordinator if any
        if self.coordinator.last_error:
            attributes["error_message"] = self.coordinator.last_error

        return attributes

    @property
    def available(self) -> bool:
        """Return if entity is available.

        The entity is always available to show error states.
        """
        return True
