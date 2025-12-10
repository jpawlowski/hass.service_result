"""
Base entity class for action_result.

This module provides the base entity class that all integration entities inherit from.
It handles common functionality like device info, unique IDs, and coordinator integration.

For more information on entities:
https://developers.home-assistant.io/docs/core/entity
https://developers.home-assistant.io/docs/core/entity/index/#common-properties
"""

from __future__ import annotations

from custom_components.action_result.const import (
    CONF_ENTITY_CATEGORY,
    CONF_NAME,
    CONF_PARENT_DEVICE,
    CONF_SERVICE_ACTION,
)
from custom_components.action_result.coordinator import ActionResultEntitiesDataUpdateCoordinator
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class ActionResultEntitiesEntity(CoordinatorEntity[ActionResultEntitiesDataUpdateCoordinator]):
    """
    Base entity class for action_result.

    All entities in this integration inherit from this class, which provides:
    - Automatic coordinator updates
    - Device info management
    - Dynamic attribution based on service domain
    - Naming conventions

    For more information:
    https://developers.home-assistant.io/docs/core/entity
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    """

    def __init__(
        self,
        coordinator: ActionResultEntitiesDataUpdateCoordinator,
    ) -> None:
        """
        Initialize the base entity.

        Args:
            coordinator: The data update coordinator for this entity.
        """
        super().__init__(coordinator)

        # Get name from config entry
        entry_name = coordinator.config_entry.data.get(CONF_NAME, coordinator.config_entry.title)

        # Check if we should associate with a parent device
        parent_device_id = coordinator.config_entry.data.get(CONF_PARENT_DEVICE, "")
        parent_device_identifiers = None

        if parent_device_id:
            # Look up the parent device in the device registry
            device_registry = dr.async_get(coordinator.hass)
            parent_device = device_registry.async_get(parent_device_id)

            if parent_device and parent_device.identifiers:
                # Use the parent device's identifiers directly
                # This makes our entity appear in the parent device's entity list
                # Multiple integrations can share the same device this way
                parent_device_identifiers = parent_device.identifiers

        # Build device info - either standalone or shared with parent device
        if parent_device_identifiers:
            # Share the parent device - our entities appear directly in its entity list
            # Add our integration identifier so we're listed as contributing to this device
            self._attr_device_info = DeviceInfo(
                identifiers=parent_device_identifiers,
                # Note: We don't set name/manufacturer/model here
                # Those come from the parent device's primary integration
            )
        else:
            # Standalone device
            self._attr_device_info = DeviceInfo(
                identifiers={
                    (
                        coordinator.config_entry.domain,
                        coordinator.config_entry.entry_id,
                    ),
                },
                name=entry_name,
                manufacturer="Action Result Entities",
                model="Action Response Bridge",
            )

    @property
    def attribution(self) -> str | None:
        """
        Return dynamic attribution based on the service action's integration.

        Attempts to get the friendly name of the integration that provides
        the service being called. Uses the integration's manifest name,
        which may be localized if the integration provides translations.

        Returns:
            Attribution string showing data source integration, or None.
        """
        # Get service action from config
        service_action = self.coordinator.config_entry.data.get(CONF_SERVICE_ACTION)
        if not service_action:
            return None

        # Extract domain from service action
        # Handle both list format (sequence) and dict format (single action)
        domain = None
        if isinstance(service_action, list):
            if service_action:
                first_action = service_action[0]
                if isinstance(first_action, dict):
                    action_str = first_action.get("action", "")
                    if "." in action_str:
                        domain = action_str.split(".", 1)[0]
        elif isinstance(service_action, dict):
            action_str = service_action.get("action", "")
            if "." in action_str:
                domain = action_str.split(".", 1)[0]

        if not domain:
            return None

        # Get the integration's friendly name from the loader
        integration_name = self._get_integration_name(domain)

        # Return attribution message
        return f"Data from the {integration_name} integration"

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category if configured.

        Returns:
            EntityCategory.CONFIG or EntityCategory.DIAGNOSTIC if configured, None otherwise.
        """
        category = self.coordinator.config_entry.data.get(CONF_ENTITY_CATEGORY)
        if category == "config":
            return EntityCategory.CONFIG
        if category == "diagnostic":
            return EntityCategory.DIAGNOSTIC
        return None

    def _get_integration_name(self, domain: str) -> str:
        """
        Get the friendly name of an integration by domain.

        Attempts to load the integration manifest and extract the name.
        Falls back to a formatted version of the domain if unavailable.

        Args:
            domain: The integration domain (e.g., 'tibber', 'homeassistant').

        Returns:
            The integration's friendly name or formatted domain.
        """
        try:
            # Try to get cached integration info
            integrations = self.hass.data.get("integrations")
            if integrations and domain in integrations:
                integration = integrations[domain]
                if hasattr(integration, "name"):
                    return integration.name
        except Exception:  # noqa: BLE001
            pass

        # Fallback: Format domain as title case
        return domain.replace("_", " ").title()
