"""Custom types for action_result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .coordinator import ActionResultEntitiesDataUpdateCoordinator


type ActionResultEntitiesConfigEntry = ConfigEntry[ActionResultEntitiesData]


@dataclass
class ActionResultEntitiesData:
    """Data for action_result."""

    coordinator: ActionResultEntitiesDataUpdateCoordinator
    integration: Integration
