"""
Core DataUpdateCoordinator implementation for action_result.

This module contains the main coordinator class that manages calling Home Assistant
services and storing the response data for sensor entities.

Error handling strategy:
- Temporary errors (network, timeout, service busy): Retry with exponential backoff
- Permanent errors (service removed, invalid config): Log and mark as unavailable

For more information on coordinators:
https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import yaml

from custom_components.action_result.const import (
    CONF_NAME,
    CONF_SERVICE_ACTION,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    ERROR_TYPE_PERMANENT,
    ERROR_TYPE_TEMPORARY,
    ERROR_TYPE_UNKNOWN,
    INITIAL_RETRY_DELAY_SECONDS,
    LOGGER,
    MAX_CONSECUTIVE_ERRORS,
    MAX_RETRY_COUNT,
    MAX_RETRY_DELAY_SECONDS,
    SERVICE_CALL_TIMEOUT_SECONDS,
)
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from custom_components.action_result.data import ActionResultEntitiesConfigEntry


class ActionResultEntitiesDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching data from Home Assistant service calls.

    This coordinator handles calling configured services and distributes
    the response data to sensor entities. It manages:
    - Periodic service calls based on update_interval
    - Error handling with retry logic for temporary failures
    - Response data distribution to entities
    - Error classification (temporary vs permanent)

    For more information:
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities

    Attributes:
        config_entry: The config entry for this integration instance.
    """

    config_entry: ActionResultEntitiesConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(*args, **kwargs)
        self.last_error: str | None = None
        self.last_error_type: str = ERROR_TYPE_UNKNOWN
        self.last_success_time: str | None = None
        self.service_response: dict[str, Any] | list[Any] | None = None
        self.consecutive_errors: int = 0
        self.is_retrying: bool = False

    def _get_service_info(self) -> tuple[str, str]:
        """
        Extract service domain and name from config entry.

        Supports both new format (service_action) and legacy format
        (service_domain + service_name).

        Returns:
            A tuple of (domain, service_name).
        """
        # Try new format first
        service_action = self.config_entry.data.get(CONF_SERVICE_ACTION)
        if service_action and isinstance(service_action, dict):
            action = service_action.get("action", "")
            if action and "." in action:
                parts = action.split(".", 1)
                return (parts[0], parts[1])

        # Fall back to legacy format
        domain = self.config_entry.data.get(CONF_SERVICE_DOMAIN, "")
        service_name = self.config_entry.data.get(CONF_SERVICE_NAME, "")
        return (domain, service_name)

    def _get_service_data(self) -> dict[str, Any]:
        """
        Extract service data from config entry.

        In HA 2025.11+, the ActionSelector stores the complete action including
        service data in the 'data' key. For backwards compatibility, also checks
        the legacy 'service_data_yaml' field.

        Returns:
            A dictionary of service data parameters.
        """
        # Try new format first: ActionSelector stores data in the 'data' key
        service_action = self.config_entry.data.get(CONF_SERVICE_ACTION)
        if service_action and isinstance(service_action, dict):
            return service_action.get("data", {}) or {}

        # Fall back to legacy YAML field for backwards compatibility
        service_data_yaml = self.config_entry.data.get("service_data_yaml", "")
        if service_data_yaml and isinstance(service_data_yaml, str) and service_data_yaml.strip():
            try:
                parsed = yaml.safe_load(service_data_yaml)
                return parsed if isinstance(parsed, dict) else {}
            except yaml.YAMLError:
                return {}

        return {}

    def _classify_error(self, exc: Exception) -> str:
        """
        Classify an error as temporary or permanent.

        Temporary errors will be retried, permanent errors require user intervention.

        Args:
            exc: The exception to classify.

        Returns:
            ERROR_TYPE_TEMPORARY, ERROR_TYPE_PERMANENT, or ERROR_TYPE_UNKNOWN.
        """
        error_str = str(exc).lower()

        # Permanent errors - require user action
        permanent_indicators = [
            "not found",
            "does not exist",
            "invalid",
            "unauthorized",
            "forbidden",
            "not supported",
            "permission denied",
            "authentication failed",
            "invalid api key",
            "missing required",
        ]
        for indicator in permanent_indicators:
            if indicator in error_str:
                return ERROR_TYPE_PERMANENT

        # Temporary errors - can be retried
        temporary_indicators = [
            "timeout",
            "timed out",
            "temporarily",
            "unavailable",
            "connection",
            "network",
            "busy",
            "rate limit",
            "too many requests",
            "server error",
            "503",
            "502",
            "504",
            "retry",
        ]
        for indicator in temporary_indicators:
            if indicator in error_str:
                return ERROR_TYPE_TEMPORARY

        # Default to unknown (treat as potentially temporary)
        return ERROR_TYPE_UNKNOWN

    async def _async_setup(self) -> None:
        """
        Set up the coordinator.

        This method is called automatically during async_config_entry_first_refresh()
        and is the ideal place for one-time initialization tasks.
        """
        service_domain, service_name = self._get_service_info()
        LOGGER.debug(
            "Coordinator setup complete for %s (service: %s.%s)",
            self.config_entry.entry_id,
            service_domain,
            service_name,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Call the configured Home Assistant service and return its response.

        This method is called automatically based on the update_interval.
        It calls the service configured in the config entry and stores
        the response for the sensor entity to expose.

        Error handling:
        - Service not found: Permanent if persistent, temporary if integration loading
        - Service call errors: Classified and retried if temporary
        - Timeouts: Temporary, will retry

        Returns:
            A dictionary containing the service response and metadata.

        Raises:
            UpdateFailed: If the service call fails.
        """
        service_domain, service_name = self._get_service_info()
        service_data = self._get_service_data()
        entry_name = self.config_entry.data.get(CONF_NAME, "Unknown")
        service_full_name = f"{service_domain}.{service_name}"

        # Verify service exists
        if not self.hass.services.has_service(service_domain, service_name):
            self.last_error = f"Service {service_full_name} not found"
            # Check if this might be temporary (integration still loading)
            # After multiple failures, treat as permanent
            if self.consecutive_errors >= MAX_RETRY_COUNT:
                self.last_error_type = ERROR_TYPE_PERMANENT
            else:
                self.last_error_type = ERROR_TYPE_TEMPORARY
                self.is_retrying = True

            self.consecutive_errors += 1
            LOGGER.warning(
                "Service %s not found for '%s' (attempt %d/%d)",
                service_full_name,
                entry_name,
                self.consecutive_errors,
                MAX_RETRY_COUNT,
            )
            raise UpdateFailed(
                translation_domain="action_result",
                translation_key="service_not_found",
                translation_placeholders={"service": service_full_name},
            )

        try:
            # Call the service with return_response=True
            LOGGER.debug(
                "Calling service %s with data: %s",
                service_full_name,
                service_data,
            )

            response = await asyncio.wait_for(
                self.hass.services.async_call(
                    domain=service_domain,
                    service=service_name,
                    service_data=service_data,
                    blocking=True,
                    return_response=True,
                ),
                timeout=SERVICE_CALL_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            self.last_error = "Service call timed out"
            self.last_error_type = ERROR_TYPE_TEMPORARY
            self.is_retrying = True
            self.consecutive_errors += 1
            LOGGER.warning(
                "Service %s timed out for '%s' (attempt %d)",
                service_full_name,
                entry_name,
                self.consecutive_errors,
            )
            raise UpdateFailed(
                translation_domain="action_result",
                translation_key="service_temporarily_unavailable",
                translation_placeholders={"service": service_full_name},
            ) from exc
        except ServiceNotFound as exc:
            self.last_error = f"Service {service_full_name} not found"
            self.last_error_type = ERROR_TYPE_PERMANENT
            self.consecutive_errors += 1
            LOGGER.error(
                "Service %s not found for '%s': %s",
                service_full_name,
                entry_name,
                exc,
            )
            raise UpdateFailed(
                translation_domain="action_result",
                translation_key="service_not_found",
                translation_placeholders={"service": service_full_name},
            ) from exc
        except HomeAssistantError as exc:
            error_msg = str(exc)
            self.last_error = error_msg
            self.last_error_type = self._classify_error(exc)
            self.consecutive_errors += 1

            if self.last_error_type == ERROR_TYPE_TEMPORARY:
                self.is_retrying = True
                LOGGER.warning(
                    "Temporary error calling service %s for '%s' (attempt %d): %s",
                    service_full_name,
                    entry_name,
                    self.consecutive_errors,
                    exc,
                )
                raise UpdateFailed(
                    translation_domain="action_result",
                    translation_key="service_temporarily_unavailable",
                    translation_placeholders={"service": service_full_name},
                ) from exc
            LOGGER.error(
                "Error calling service %s for '%s': %s",
                service_full_name,
                entry_name,
                exc,
            )
            raise UpdateFailed(
                translation_domain="action_result",
                translation_key="service_call_failed",
                translation_placeholders={
                    "service": service_full_name,
                    "error": error_msg,
                },
            ) from exc
        except Exception as exc:
            error_msg = str(exc)
            self.last_error = error_msg
            self.last_error_type = self._classify_error(exc)
            self.consecutive_errors += 1

            LOGGER.exception(
                "Unexpected error calling service %s for '%s'",
                service_full_name,
                entry_name,
            )
            raise UpdateFailed(
                translation_domain="action_result",
                translation_key="service_call_failed",
                translation_placeholders={
                    "service": service_full_name,
                    "error": error_msg,
                },
            ) from exc
        else:
            # Success - reset error state
            self.service_response = response
            self.last_error = None
            self.last_error_type = ERROR_TYPE_UNKNOWN
            self.consecutive_errors = 0
            self.is_retrying = False
            self.last_success_time = dt_util.utcnow().isoformat()

            LOGGER.debug(
                "Service %s returned response for '%s': %s",
                service_full_name,
                entry_name,
                type(response).__name__,
            )

            return {
                "response": response,
                "service": service_full_name,
                "last_update": self.last_success_time,
                "success": True,
                "error": None,
                "error_type": None,
                "consecutive_errors": 0,
            }

    def get_retry_delay(self) -> int:
        """
        Calculate the retry delay based on consecutive errors.

        Uses exponential backoff with a maximum delay.

        Returns:
            Delay in seconds before the next retry.
        """
        if self.consecutive_errors <= 0:
            return 0

        # Cap consecutive_errors to prevent overflow in exponential calculation
        capped_errors = min(self.consecutive_errors, MAX_CONSECUTIVE_ERRORS)

        # Exponential backoff: 30, 60, 120, 240... up to MAX_RETRY_DELAY_SECONDS
        return min(
            INITIAL_RETRY_DELAY_SECONDS * (2 ** (capped_errors - 1)),
            MAX_RETRY_DELAY_SECONDS,
        )
