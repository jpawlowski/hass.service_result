"""
Custom integration to integrate service_result with Home Assistant.

This integration exposes sensor entities whose attributes are populated from
the response data of Home Assistant services/actions. Each config entry defines
which service to call and the sensor's `data` attribute contains the full
service response.

For more details about this integration, please refer to:
https://github.com/jpawlowski/hass.service_result

For integration development guidelines:
https://developers.home-assistant.io/docs/creating_integration_manifest
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_loaded_integration

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN, LOGGER
from .coordinator import ServiceResultEntitiesDataUpdateCoordinator
from .data import ServiceResultEntitiesData

if TYPE_CHECKING:
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

    Data flow in this integration:
    1. User configures service domain, service name, and YAML data in config flow
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
    # Get scan interval from options, fall back to default
    scan_interval_seconds = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

    # Initialize coordinator with config_entry
    coordinator = ServiceResultEntitiesDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}",
        config_entry=entry,
        update_interval=timedelta(seconds=scan_interval_seconds),
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
