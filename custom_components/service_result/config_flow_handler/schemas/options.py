"""
Options flow schemas.

Schemas for the options flow that allows users to modify settings
after initial configuration.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from custom_components.service_result.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SERVICE_DATA_YAML,
    CONF_SERVICE_DOMAIN,
    CONF_SERVICE_NAME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from homeassistant.helpers import selector


def get_options_schema(
    defaults: Mapping[str, Any] | None = None,
    entry_data: Mapping[str, Any] | None = None,
) -> vol.Schema:
    """
    Get schema for options flow.

    Args:
        defaults: Optional dictionary of current option values.
        entry_data: Optional dictionary of current config entry data.

    Returns:
        Voluptuous schema for options configuration.
    """
    defaults = defaults or {}
    entry_data = entry_data or {}

    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=entry_data.get(CONF_NAME, "Service Result"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Required(
                CONF_SERVICE_DOMAIN,
                default=entry_data.get(CONF_SERVICE_DOMAIN, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Required(
                CONF_SERVICE_NAME,
                default=entry_data.get(CONF_SERVICE_NAME, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                ),
            ),
            vol.Optional(
                CONF_SERVICE_DATA_YAML,
                default=entry_data.get(CONF_SERVICE_DATA_YAML, ""),
            ): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.TEXT,
                    multiline=True,
                ),
            ),
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=10,
                    max=86400,
                    step=1,
                    unit_of_measurement="s",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
        },
    )


__all__ = [
    "get_options_schema",
]
