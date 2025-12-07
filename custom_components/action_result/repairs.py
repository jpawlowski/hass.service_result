"""Repairs platform for action_result.

Currently, this integration does not create any repair issues.
This file provides the infrastructure for future repair flows if needed.
"""

from __future__ import annotations

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow based on the issue_id."""
    # Fallback for unknown issue IDs
    return UnknownIssueRepairFlow(issue_id)


class UnknownIssueRepairFlow(RepairsFlow):
    """Handler for unknown repair issues."""

    def __init__(self, issue_id: str) -> None:
        """Initialize the unknown issue repair flow."""
        super().__init__()
        self._issue_id = issue_id

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle unknown issues."""
        if user_input is not None:
            # Just acknowledge and close
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")
