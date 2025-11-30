"""Custom types for service_result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import ServiceResultEntitiesApiClient
    from .coordinator import ServiceResultEntitiesDataUpdateCoordinator


type ServiceResultEntitiesConfigEntry = ConfigEntry[ServiceResultEntitiesData]


@dataclass
class ServiceResultEntitiesData:
    """Data for service_result."""

    client: ServiceResultEntitiesApiClient
    coordinator: ServiceResultEntitiesDataUpdateCoordinator
    integration: Integration
