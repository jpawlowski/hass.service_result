"""
Base entity class for action_result.

This module provides the base entity class that all integration entities inherit from.
It handles common functionality like device info, unique IDs, and coordinator integration.

For more information on entities:
https://developers.home-assistant.io/docs/core/entity
https://developers.home-assistant.io/docs/core/entity/index/#common-properties
"""

from __future__ import annotations

from custom_components.action_result.const import ATTRIBUTION, CONF_NAME
from custom_components.action_result.coordinator import ActionResultEntitiesDataUpdateCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class ActionResultEntitiesEntity(CoordinatorEntity[ActionResultEntitiesDataUpdateCoordinator]):
    """
    Base entity class for action_result.

    All entities in this integration inherit from this class, which provides:
    - Automatic coordinator updates
    - Device info management
    - Attribution and naming conventions

    For more information:
    https://developers.home-assistant.io/docs/core/entity
    https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    """

    _attr_attribution = ATTRIBUTION

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

        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    coordinator.config_entry.domain,
                    coordinator.config_entry.entry_id,
                ),
            },
            name=entry_name,
            manufacturer="Action Result Entities",
            model="Service Response Bridge",
        )
