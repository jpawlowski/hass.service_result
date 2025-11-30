"""
Custom integration to integrate service_result with Home Assistant.

This integration exposes sensor entities whose attributes are populated from
the response data of Home Assistant services/actions. Each config entry defines
which service to call and the sensor's `data` attribute contains the full
service response.

Supports three update modes:
- Polling: Cyclic updates at a configurable interval
- Manual: Update via homeassistant.update_entity service call
- State Trigger: Update when a watched entity's state changes

For more details about this integration, please refer to:
https://github.com/jpawlowski/hass.service_result

For integration development guidelines:
https://developers.home-assistant.io/docs/creating_integration_manifest
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import Event, EventStateChangedData, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.loader import async_get_loaded_integration

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_ACTION,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UPDATE_MODE,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    DOMAIN,
    LOGGER,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
)
from .coordinator import ServiceResultEntitiesDataUpdateCoordinator
from .data import ServiceResultEntitiesData

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .data import ServiceResultEntitiesConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

# This integration is configured via config entries only
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """
    Set up the integration.

    This is called once at Home Assistant startup.

    Args:
        hass: The Home Assistant instance.
        config: The Home Assistant configuration.

    Returns:
        True if setup was successful.
    """
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """
    Migrate old config entry to new version.

    This handles migration from VERSION 1 (separate domain/name fields)
    to VERSION 2 (action selector format).

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry to migrate.

    Returns:
        True if migration was successful.
    """
    LOGGER.debug("Migrating config entry from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migrate from v1 (service_domain + service_name) to v2 (service_action)
        old_data = dict(config_entry.data)

        service_domain = old_data.pop(CONF_SERVICE_DOMAIN, "")
        service_name = old_data.pop(CONF_SERVICE_NAME, "")

        # Build the new action selector format
        if service_domain and service_name:
            action_value = f"{service_domain}.{service_name}"
            old_data[CONF_SERVICE_ACTION] = {"action": action_value}

        hass.config_entries.async_update_entry(
            config_entry,
            data=old_data,
            version=2,
        )

        LOGGER.info(
            "Migrated config entry %s from version 1 to version 2",
            config_entry.entry_id,
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ServiceResultEntitiesConfigEntry,
) -> bool:
    """
    Set up this integration using UI.

    This is called when a config entry is loaded. It:
    1. Initializes the DataUpdateCoordinator for calling services
    2. Performs the first data refresh
    3. Sets up the sensor platform
    4. Sets up reload listener for config changes
    5. Sets up state change listener if using state trigger mode

    Data flow in this integration:
    1. User configures service via action selector and YAML data in config flow
    2. Configuration stored in entry.data
    3. Coordinator calls the configured service with return_response=True
    4. Service response stored in coordinator.data
    5. Sensor entity exposes the response via its 'data' attribute

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being set up.

    Returns:
        True if setup was successful.
    """
    # Get update mode and scan interval from config
    update_mode = entry.data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE)
    scan_interval_seconds = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

    # Determine update_interval based on mode
    # For manual and state_trigger modes, we don't want automatic polling
    if update_mode == UPDATE_MODE_POLLING:
        update_interval = timedelta(seconds=scan_interval_seconds)
    else:
        # No automatic updates for manual or state trigger modes
        update_interval = None

    # Initialize coordinator with config_entry
    coordinator = ServiceResultEntitiesDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        config_entry=entry,
        update_interval=update_interval,
        always_update=True,  # Always update entities to reflect latest service response
    )

    # Store runtime data
    entry.runtime_data = ServiceResultEntitiesData(
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Set up state change listener for state_trigger mode
    if update_mode == UPDATE_MODE_STATE_TRIGGER:
        trigger_entity = entry.data.get(CONF_TRIGGER_ENTITY, "")
        if trigger_entity:
            trigger_from_state = entry.data.get(CONF_TRIGGER_FROM_STATE, "")
            trigger_to_state = entry.data.get(CONF_TRIGGER_TO_STATE, "")

            @callback
            def async_state_change_listener(event: Event[EventStateChangedData]) -> None:
                """Handle state changes of the trigger entity."""
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")

                if new_state is None:
                    return

                old_state_value = old_state.state if old_state else None
                new_state_value = new_state.state

                # Check if the state change matches our criteria
                should_trigger = True

                # Check from_state filter
                if trigger_from_state and old_state_value != trigger_from_state:
                    should_trigger = False

                # Check to_state filter
                if trigger_to_state and new_state_value != trigger_to_state:
                    should_trigger = False

                if should_trigger:
                    LOGGER.debug(
                        "State trigger activated for %s: %s -> %s",
                        trigger_entity,
                        old_state_value,
                        new_state_value,
                    )
                    # Schedule a coordinator refresh
                    hass.async_create_task(coordinator.async_request_refresh())

            # Track state changes for the trigger entity
            entry.async_on_unload(
                async_track_state_change_event(
                    hass,
                    [trigger_entity],
                    async_state_change_listener,
                )
            )

            LOGGER.info(
                "Set up state trigger for entity %s (from: %s, to: %s)",
                trigger_entity,
                trigger_from_state or "any",
                trigger_to_state or "any",
            )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ServiceResultEntitiesConfigEntry,
) -> bool:
    """
    Unload a config entry.

    This is called when the integration is being removed or reloaded.
    It ensures proper cleanup of all platform entities.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        True if unload was successful.
    """
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ServiceResultEntitiesConfigEntry,
) -> None:
    """
    Reload config entry.

    This is called when the integration configuration or options have changed.
    It unloads and then reloads the integration with the new configuration.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being reloaded.
    """
    await hass.config_entries.async_reload(entry.entry_id)
