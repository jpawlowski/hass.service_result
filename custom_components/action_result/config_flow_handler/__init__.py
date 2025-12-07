"""
Config flow handler package for action_result.

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

    from .config_flow_handler import ActionResultEntitiesConfigFlowHandler

For more information:
https://developers.home-assistant.io/docs/config_entries_config_flow_handler
"""

from __future__ import annotations

from .config_flow import ActionResultEntitiesConfigFlowHandler
from .options_flow import ActionResultEntitiesOptionsFlow

__all__ = [
    "ActionResultEntitiesConfigFlowHandler",
    "ActionResultEntitiesOptionsFlow",
]
