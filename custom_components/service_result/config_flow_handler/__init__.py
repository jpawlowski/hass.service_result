"""
Config flow handler package for service_result.

This package implements the configuration flows for the integration, organized
for maintainability and scalability.

Package structure:
------------------
- config_flow.py: Main configuration flow (user setup, reconfigure)
- options_flow.py: Options flow for post-setup configuration changes
- schemas/: Voluptuous schemas for all forms

Usage:
------
The main config flow handler is imported in config_flow.py at the integration root:

    from .config_flow_handler import ServiceResultEntitiesConfigFlowHandler

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from .config_flow import ServiceResultEntitiesConfigFlowHandler
from .options_flow import ServiceResultEntitiesOptionsFlow

__all__ = [
    "ServiceResultEntitiesConfigFlowHandler",
    "ServiceResultEntitiesOptionsFlow",
]
