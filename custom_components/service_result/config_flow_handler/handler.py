"""
Config flow handler for service_result.

This module provides backwards compatibility by re-exporting the flow handlers
from their respective modules. The actual implementation is split across:

- config_flow.py: Main config flow (user, reconfigure)
- options_flow.py: Options flow for post-setup configuration
- schemas/: Voluptuous schemas for all forms

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from custom_components.service_result.config_flow_handler.config_flow import ServiceResultEntitiesConfigFlowHandler
from custom_components.service_result.config_flow_handler.options_flow import ServiceResultEntitiesOptionsFlow

# Re-export for backwards compatibility and external imports
__all__ = [
    "ServiceResultEntitiesConfigFlowHandler",
    "ServiceResultEntitiesOptionsFlow",
]
