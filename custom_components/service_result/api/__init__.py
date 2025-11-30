"""API package for service_result."""

from .client import (
    ServiceResultEntitiesApiClient,
    ServiceResultEntitiesApiClientAuthenticationError,
    ServiceResultEntitiesApiClientCommunicationError,
    ServiceResultEntitiesApiClientError,
)

__all__ = [
    "ServiceResultEntitiesApiClient",
    "ServiceResultEntitiesApiClientAuthenticationError",
    "ServiceResultEntitiesApiClientCommunicationError",
    "ServiceResultEntitiesApiClientError",
]
