"""
Custom integration to integrate action_result with Home Assistant.

This integration exposes sensor entities whose attributes are populated from
the response data of Home Assistant services/actions. Each config entry defines
which service to call and the sensor's `data` attribute contains the full
service response.

Supports three update modes:
- Polling: Cyclic updates at a configurable interval
- Manual: Update via homeassistant.update_entity service call
- State Trigger: Update when a watched entity's state changes

For more details about this integration, please refer to:
https://github.com/jpawlowski/hass.action_result

For integration development guidelines:
https://developers.home-assistant.io/docs/creating_integration_manifest
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.core import Event, EventStateChangedData, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.loader import async_get_loaded_integration

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SENSOR_TYPE,
    CONF_SERVICE_ACTION,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    CONF_TRIGGER_ENTITY,
    CONF_TRIGGER_FROM_STATE,
    CONF_TRIGGER_TO_STATE,
    CONF_UPDATE_MODE,
    CONF_VALUE_TYPE,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DEFAULT_UPDATE_MODE,
    DOMAIN,
    LOGGER,
    REPAIR_ISSUE_TRIGGER_ENTITY_MISSING,
    SENSOR_TYPE_DATA,
    SENSOR_TYPE_VALUE,
    UPDATE_MODE_POLLING,
    UPDATE_MODE_STATE_TRIGGER,
    VALUE_TYPE_BOOLEAN,
)
from .coordinator import ActionResultEntitiesDataUpdateCoordinator
from .data import ActionResultEntitiesData

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .data import ActionResultEntitiesConfigEntry


# Determine platforms based on sensor type
def _get_platforms_for_entry(entry: ConfigEntry) -> list[Platform]:
    """Get the platforms to set up based on sensor type."""
    sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DATA)
    value_type = entry.data.get(CONF_VALUE_TYPE, "")

    # Binary sensor for boolean values
    if sensor_type == SENSOR_TYPE_VALUE and value_type == VALUE_TYPE_BOOLEAN:
        return [Platform.BINARY_SENSOR]

    # Regular sensor for everything else
    return [Platform.SENSOR]


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
    entry: ActionResultEntitiesConfigEntry,
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
    4. Action response stored in coordinator.data
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
    coordinator = ActionResultEntitiesDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        config_entry=entry,
        update_interval=update_interval,
        always_update=True,  # Always update entities to reflect latest service response
    )

    # Store runtime data
    entry.runtime_data = ActionResultEntitiesData(
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # Check if the target service exists before attempting first refresh
    # This ensures we don't fail if the service's integration hasn't loaded yet
    service_domain, service_name = coordinator.get_service_info()
    if not hass.services.has_service(service_domain, service_name):
        LOGGER.info(
            "Service %s.%s not yet available, will retry setup",
            service_domain,
            service_name,
        )
        raise ConfigEntryNotReady(
            f"Service {service_domain}.{service_name} not yet available. "
            f"The {service_domain} integration may still be loading."
        )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    # If first refresh fails with UpdateFailed, treat as ConfigEntryNotReady
    # so Home Assistant will retry the setup later
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as exc:
        # Convert any exception during first refresh to ConfigEntryNotReady
        # This ensures HA will retry setup instead of marking entry as failed
        raise ConfigEntryNotReady(f"Failed to fetch initial data from {service_domain}.{service_name}: {exc}") from exc

    # Set up platforms based on sensor type
    platforms = _get_platforms_for_entry(entry)
    await hass.config_entries.async_forward_entry_setups(entry, platforms)

    # Set up service registry listener to handle service removal at runtime
    @callback
    def async_service_removed_listener(event: Event) -> None:
        """Handle service removal events."""
        removed_domain = event.data.get("domain")
        removed_service = event.data.get("service")

        if removed_domain == service_domain and removed_service == service_name:
            LOGGER.warning(
                "Service %s.%s was removed, entities will become unavailable",
                service_domain,
                service_name,
            )
            # The coordinator will automatically mark entities as unavailable
            # when the next update attempt fails

    # Listen for service removal events
    entry.async_on_unload(
        hass.bus.async_listen(
            "service_removed",
            async_service_removed_listener,
        )
    )

    # Set up state change listener for state_trigger mode
    if update_mode == UPDATE_MODE_STATE_TRIGGER:
        trigger_entity = entry.data.get(CONF_TRIGGER_ENTITY, "")
        if trigger_entity:
            # Check if trigger entity exists
            if not hass.states.get(trigger_entity):
                # Create repair issue for missing trigger entity
                entry_name = entry.data.get("name", "Unknown")
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    f"{REPAIR_ISSUE_TRIGGER_ENTITY_MISSING}_{entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="trigger_entity_missing",
                    translation_placeholders={
                        "entry_name": entry_name,
                        "trigger_entity": trigger_entity,
                    },
                )
                LOGGER.warning(
                    "Trigger entity %s not found for config entry %s (%s). "
                    "The integration will not update automatically until the entity becomes available.",
                    trigger_entity,
                    entry_name,
                    entry.entry_id,
                )

            trigger_from_state = entry.data.get(CONF_TRIGGER_FROM_STATE, "")
            trigger_to_state = entry.data.get(CONF_TRIGGER_TO_STATE, "")

            @callback
            def async_state_change_listener(event: Event[EventStateChangedData]) -> None:
                """Handle state changes of the trigger entity."""
                old_state = event.data.get("old_state")
                new_state = event.data.get("new_state")

                if new_state is None:
                    # Entity was removed - create repair issue if it doesn't exist
                    entry_name = entry.data.get("name", "Unknown")
                    issue_id = f"{REPAIR_ISSUE_TRIGGER_ENTITY_MISSING}_{entry.entry_id}"

                    # Check if issue already exists
                    existing_issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
                    if not existing_issue:
                        ir.async_create_issue(
                            hass,
                            DOMAIN,
                            issue_id,
                            is_fixable=False,
                            severity=ir.IssueSeverity.WARNING,
                            translation_key="trigger_entity_missing",
                            translation_placeholders={
                                "entry_name": entry_name,
                                "trigger_entity": trigger_entity,
                            },
                        )
                        LOGGER.warning(
                            "Trigger entity %s was removed for config entry %s (%s)",
                            trigger_entity,
                            entry_name,
                            entry.entry_id,
                        )
                    return

                # Entity exists - delete repair issue if it exists
                issue_id = f"{REPAIR_ISSUE_TRIGGER_ENTITY_MISSING}_{entry.entry_id}"
                existing_issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
                if existing_issue:
                    ir.async_delete_issue(hass, DOMAIN, issue_id)
                    LOGGER.info(
                        "Trigger entity %s is now available again, repair issue removed",
                        trigger_entity,
                    )

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
                    # Schedule a coordinator refresh using config entry task management
                    entry.async_create_background_task(
                        hass,
                        coordinator.async_request_refresh(),
                        f"action_result_{entry.entry_id}_refresh",
                    )

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
    entry: ActionResultEntitiesConfigEntry,
) -> bool:
    """
    Unload a config entry.

    This is called when the integration is being removed or reloaded.
    It ensures proper cleanup of all platform entities and repair issues.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being unloaded.

    Returns:
        True if unload was successful.
    """
    # Clean up any repair issues for this entry
    issue_id = f"{REPAIR_ISSUE_TRIGGER_ENTITY_MISSING}_{entry.entry_id}"
    existing_issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    if existing_issue:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        LOGGER.debug("Removed repair issue %s during unload", issue_id)

    platforms = _get_platforms_for_entry(entry)
    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ActionResultEntitiesConfigEntry,
) -> None:
    """
    Reload config entry.

    This is called when the integration configuration or options have changed.
    It merges options into config entry data and then reloads the integration.

    Options flow allows changing:
    - Update mode (polling, manual, state_trigger)
    - Mode-specific settings (scan_interval, trigger_entity, etc.)

    These changes are merged into entry.data to ensure they're used on next load.

    Args:
        hass: The Home Assistant instance.
        entry: The config entry being reloaded.
    """
    # Merge options into data if options were changed
    if entry.options:
        new_data = dict(entry.data)

        # Update mode and mode-specific settings from options
        if CONF_UPDATE_MODE in entry.options:
            new_data[CONF_UPDATE_MODE] = entry.options[CONF_UPDATE_MODE]

        if CONF_SCAN_INTERVAL in entry.options:
            new_data[CONF_SCAN_INTERVAL] = entry.options[CONF_SCAN_INTERVAL]

        if CONF_TRIGGER_ENTITY in entry.options:
            new_data[CONF_TRIGGER_ENTITY] = entry.options[CONF_TRIGGER_ENTITY]

        if CONF_TRIGGER_FROM_STATE in entry.options:
            new_data[CONF_TRIGGER_FROM_STATE] = entry.options[CONF_TRIGGER_FROM_STATE]

        if CONF_TRIGGER_TO_STATE in entry.options:
            new_data[CONF_TRIGGER_TO_STATE] = entry.options[CONF_TRIGGER_TO_STATE]

        # Update the config entry with merged data
        hass.config_entries.async_update_entry(entry, data=new_data, options={})

        LOGGER.debug(
            "Merged options into config entry data for %s: update_mode=%s",
            entry.entry_id,
            new_data.get(CONF_UPDATE_MODE, DEFAULT_UPDATE_MODE),
        )

    await hass.config_entries.async_reload(entry.entry_id)
