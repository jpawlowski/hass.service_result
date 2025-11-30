"""Diagnostics support for service_result.

Learn more about diagnostics:
https://developers.home-assistant.io/docs/core/integration_diagnostics
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_SERVICE_DATA_YAML

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import ServiceResultEntitiesConfigEntry

# Fields to redact from diagnostics - CRITICAL for security!
# The service data YAML may contain sensitive information
TO_REDACT = {
    CONF_SERVICE_DATA_YAML,
    "password",
    "api_key",
    "token",
    "secret",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ServiceResultEntitiesConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    integration = entry.runtime_data.integration

    # Get device and entity information
    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    # Find all devices for this integration
    devices = dr.async_entries_for_config_entry(device_reg, entry.entry_id)
    device_info = []
    for device in devices:
        entities = er.async_entries_for_device(entity_reg, device.id)
        device_info.append(
            {
                "id": device.id,
                "name": device.name,
                "manufacturer": device.manufacturer,
                "model": device.model,
                "entity_count": len(entities),
                "entities": [
                    {
                        "entity_id": entity.entity_id,
                        "platform": entity.platform,
                        "original_name": entity.original_name,
                        "disabled": entity.disabled,
                        "disabled_by": (entity.disabled_by.value if entity.disabled_by else None),
                    }
                    for entity in entities
                ],
            }
        )

    # Coordinator statistics
    coordinator_info = {
        "last_update_success": coordinator.last_update_success,
        "update_interval": str(coordinator.update_interval),
        "last_error": coordinator.last_error,
        "last_success_time": coordinator.last_success_time,
    }

    # Integration information
    integration_info = {
        "name": integration.name,
        "version": integration.version,
        "domain": integration.domain,
    }

    # Config entry details (with redacted sensitive data)
    entry_info = {
        "entry_id": entry.entry_id,
        "version": entry.version,
        "minor_version": entry.minor_version,
        "domain": entry.domain,
        "title": entry.title,
        "state": str(entry.state),
        "unique_id": entry.unique_id,
        "disabled_by": entry.disabled_by.value if entry.disabled_by else None,
        "data": async_redact_data(entry.data, TO_REDACT),
        "options": async_redact_data(entry.options, TO_REDACT),
    }

    # Error information
    error_info = {
        "last_exception": (str(coordinator.last_exception) if coordinator.last_exception else None),
        "last_exception_type": (type(coordinator.last_exception).__name__ if coordinator.last_exception else None),
    }

    # Data sample info (not the actual data to avoid exposing sensitive info)
    data_sample = {}
    if coordinator.data:
        if isinstance(coordinator.data, dict):
            data_sample = {
                "has_response": "response" in coordinator.data,
                "success": coordinator.data.get("success"),
                "last_update": coordinator.data.get("last_update"),
            }

    return {
        "entry": entry_info,
        "integration": integration_info,
        "coordinator": coordinator_info,
        "devices": device_info,
        "data_sample": data_sample,
        "error": error_info,
    }
