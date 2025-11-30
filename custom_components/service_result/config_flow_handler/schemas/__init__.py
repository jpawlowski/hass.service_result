"""
Data schemas for config flow forms.

This package contains all voluptuous schemas used in config flows.
Schemas are organized into separate modules for better maintainability.

All schemas are re-exported from this __init__.py for convenient imports.
"""

from __future__ import annotations

from custom_components.service_result.config_flow_handler.schemas.config import get_reconfigure_schema, get_user_schema

# Re-export all schemas for convenient imports
__all__ = [
    "get_reconfigure_schema",
    "get_user_schema",
]
