"""
Data update coordinator package for service_result.

This package provides the coordinator infrastructure for managing periodic
service calls and distributing responses to all entities in the integration.

For more information on coordinators:
https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
"""

from __future__ import annotations

from .base import ServiceResultEntitiesDataUpdateCoordinator

__all__ = ["ServiceResultEntitiesDataUpdateCoordinator"]
