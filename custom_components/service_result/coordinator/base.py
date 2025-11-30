"""
Core DataUpdateCoordinator implementation for service_result.

This module contains the main coordinator class that manages calling Home Assistant
services and storing the response data for sensor entities.

For more information on coordinators:
https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml

from custom_components.service_result.const import (
    CONF_NAME,
    CONF_SERVICE_DATA_YAML,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    LOGGER,
)
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.service_result.data import ServiceResultEntitiesConfigEntry


class ServiceResultEntitiesDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching data from Home Assistant service calls.

    This coordinator handles calling configured services and distributes
    the response data to sensor entities. It manages:
    - Periodic service calls based on update_interval
    - Error handling and recovery
    - Response data distribution to entities

    For more information:
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities

    Attributes:
        config_entry: The config entry for this integration instance.
    """

    config_entry: ServiceResultEntitiesConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(*args, **kwargs)
        self.last_error: str | None = None
        self.last_success_time: str | None = None
        self.service_response: dict[str, Any] | list[Any] | None = None

    async def _async_setup(self) -> None:
        """
        Set up the coordinator.

        This method is called automatically during async_config_entry_first_refresh()
        and is the ideal place for one-time initialization tasks.
        """
        LOGGER.debug(
            "Coordinator setup complete for %s (service: %s.%s)",
            self.config_entry.entry_id,
            self.config_entry.data.get(CONF_SERVICE_DOMAIN),
            self.config_entry.data.get(CONF_SERVICE_NAME),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Call the configured Home Assistant service and return its response.

        This method is called automatically based on the update_interval.
        It calls the service configured in the config entry and stores
        the response for the sensor entity to expose.

        Returns:
            A dictionary containing the service response and metadata.

        Raises:
            UpdateFailed: If the service call fails.
        """
        service_domain = self.config_entry.data.get(CONF_SERVICE_DOMAIN, "")
        service_name = self.config_entry.data.get(CONF_SERVICE_NAME, "")
        service_data_yaml = self.config_entry.data.get(CONF_SERVICE_DATA_YAML, "")
        entry_name = self.config_entry.data.get(CONF_NAME, "Unknown")

        # Parse YAML service data
        try:
            if service_data_yaml.strip():
                service_data = yaml.safe_load(service_data_yaml)
                if service_data is None:
                    service_data = {}
            else:
                service_data = {}
        except yaml.YAMLError as exc:
            self.last_error = f"Invalid YAML: {exc}"
            LOGGER.error(
                "Failed to parse service data YAML for '%s': %s",
                entry_name,
                exc,
            )
            raise UpdateFailed(
                translation_domain="service_result",
                translation_key="yaml_parse_error",
            ) from exc

        # Verify service exists
        if not self.hass.services.has_service(service_domain, service_name):
            self.last_error = f"Service {service_domain}.{service_name} not found"
            LOGGER.error(
                "Service %s.%s not found for '%s'",
                service_domain,
                service_name,
                entry_name,
            )
            raise UpdateFailed(
                translation_domain="service_result",
                translation_key="service_not_found",
            )

        try:
            # Call the service with return_response=True
            LOGGER.debug(
                "Calling service %s.%s with data: %s",
                service_domain,
                service_name,
                service_data,
            )

            response = await self.hass.services.async_call(
                domain=service_domain,
                service=service_name,
                service_data=service_data,
                blocking=True,
                return_response=True,
            )
        except ServiceNotFound as exc:
            self.last_error = f"Service {service_domain}.{service_name} not found"
            LOGGER.error(
                "Service %s.%s not found for '%s': %s",
                service_domain,
                service_name,
                entry_name,
                exc,
            )
            raise UpdateFailed(
                translation_domain="service_result",
                translation_key="service_not_found",
            ) from exc
        except HomeAssistantError as exc:
            self.last_error = str(exc)
            LOGGER.error(
                "Error calling service %s.%s for '%s': %s",
                service_domain,
                service_name,
                entry_name,
                exc,
            )
            raise UpdateFailed(
                translation_domain="service_result",
                translation_key="service_call_failed",
            ) from exc
        except Exception as exc:
            self.last_error = str(exc)
            LOGGER.exception(
                "Unexpected error calling service %s.%s for '%s'",
                service_domain,
                service_name,
                entry_name,
            )
            raise UpdateFailed(
                translation_domain="service_result",
                translation_key="service_call_failed",
            ) from exc
        else:
            # Store response and update metadata
            self.service_response = response
            self.last_error = None
            self.last_success_time = dt_util.utcnow().isoformat()

            LOGGER.debug(
                "Service %s.%s returned response for '%s': %s",
                service_domain,
                service_name,
                entry_name,
                type(response).__name__,
            )

            return {
                "response": response,
                "service": f"{service_domain}.{service_name}",
                "last_update": self.last_success_time,
                "success": True,
                "error": None,
            }
