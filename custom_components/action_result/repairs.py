"""Repairs platform for action_result.

This module provides repair flows for various integration issues:
- Missing trigger entities in state_trigger mode
- Service not found (integration removed/disabled)
- Service call failures
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.data_entry_flow import FlowResult

from .const import REPAIR_ISSUE_ENUM_VALUE_ADDED, REPAIR_ISSUE_TRIGGER_ENTITY_MISSING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create a repair flow based on the issue_id."""
    if issue_id.startswith(REPAIR_ISSUE_TRIGGER_ENTITY_MISSING):
        return TriggerEntityMissingRepairFlow(issue_id, data)

    # Enum value added issues
    if issue_id.startswith(REPAIR_ISSUE_ENUM_VALUE_ADDED):
        return EnumValueAddedRepairFlow(issue_id, data)

    # Service not found issues - extract config_entry_id from issue_id
    if "_service_not_found" in issue_id:
        config_entry_id = issue_id.replace("_service_not_found", "")
        return ServiceNotFoundRepairFlow(issue_id, data, config_entry_id)

    # Service call failure issues
    if "_service_call_failed" in issue_id:
        config_entry_id = issue_id.replace("_service_call_failed", "")
        return ServiceCallFailedRepairFlow(issue_id, data, config_entry_id)

    # Fallback for unknown issue IDs
    return UnknownIssueRepairFlow(issue_id)


class TriggerEntityMissingRepairFlow(RepairsFlow):
    """Handler for missing trigger entity issues."""

    def __init__(
        self,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the trigger entity missing repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data or {}

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle trigger entity missing issue.

        This flow guides the user to reconfigure the integration
        with a valid trigger entity.
        """
        if user_input is not None:
            # User acknowledged, close the repair issue
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")


class ServiceNotFoundRepairFlow(RepairsFlow):
    """Handler for service not found issues.

    Offers the user options to:
    1. Delete the config entry
    2. Reconfigure with a different service
    3. Ignore (if they plan to reinstall the integration)
    """

    def __init__(
        self,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
        config_entry_id: str,
    ) -> None:
        """Initialize the service not found repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data or {}
        self._config_entry_id = config_entry_id

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle service not found issue - present options to user."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "delete_entry":
                return await self.async_step_confirm_delete()
            if action == "reconfigure":
                return await self.async_step_reconfigure()
            if action == "ignore":
                # User wants to ignore for now (maybe reinstalling integration)
                return self.async_create_entry(data={})

        return self.async_show_menu(
            step_id="init",
            menu_options=["delete_entry", "reconfigure", "ignore"],
        )

    async def async_step_delete_entry(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Confirm deletion of the config entry."""
        return await self.async_step_confirm_delete(user_input)

    async def async_step_confirm_delete(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Confirm deletion of the config entry."""
        if user_input is not None:
            # Delete the config entry
            entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
            if entry:
                await self.hass.config_entries.async_remove(entry.entry_id)
            return self.async_create_entry(data={})

        # Convert data to string placeholders
        placeholders = {k: str(v) for k, v in self._data.items() if v is not None}

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Start reconfiguration flow."""
        # Trigger reconfigure flow for the config entry
        entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
        if entry:
            # Start the reconfigure flow
            return self.async_external_step(
                step_id="reconfigure",
                url=f"/config/integrations/integration/{entry.domain}",
            )

        # Entry not found, just close the repair
        return self.async_create_entry(data={})

    async def async_step_ignore(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Ignore the issue for now."""
        return self.async_create_entry(data={})


class ServiceCallFailedRepairFlow(RepairsFlow):
    """Handler for persistent service call failures.

    Guides the user to reconfigure or delete the entry.
    """

    def __init__(
        self,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
        config_entry_id: str,
    ) -> None:
        """Initialize the service call failed repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data or {}
        self._config_entry_id = config_entry_id

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle service call failure - suggest fixes."""
        if user_input is not None:
            action = user_input.get("action")

            if action == "reconfigure":
                return await self.async_step_reconfigure()
            if action == "delete_entry":
                return await self.async_step_confirm_delete()
            if action == "ignore":
                return self.async_create_entry(data={})

        return self.async_show_menu(
            step_id="init",
            menu_options=["reconfigure", "delete_entry", "ignore"],
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Start reconfiguration flow."""
        entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
        if entry:
            return self.async_external_step(
                step_id="reconfigure",
                url=f"/config/integrations/integration/{entry.domain}",
            )
        return self.async_create_entry(data={})

    async def async_step_confirm_delete(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Confirm deletion of the config entry."""
        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self._config_entry_id)
            if entry:
                await self.hass.config_entries.async_remove(entry.entry_id)
            return self.async_create_entry(data={})

        # Convert data to string placeholders
        placeholders = {k: str(v) for k, v in self._data.items() if v is not None}

        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    async def async_step_delete_entry(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Delete entry step."""
        return await self.async_step_confirm_delete(user_input)

    async def async_step_ignore(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Ignore the issue."""
        return self.async_create_entry(data={})


class EnumValueAddedRepairFlow(RepairsFlow):
    """Handler for enum value added issues.

    Notifies user that new enum values were discovered and translations should be added.
    """

    def __init__(
        self,
        issue_id: str,
        data: dict[str, str | int | float | None] | None,
    ) -> None:
        """Initialize the enum value added repair flow."""
        super().__init__()
        self._issue_id = issue_id
        self._data = data or {}

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle enum value added issue.

        Informs the user that new enum values were discovered and added.
        The user should add translations via the config entry reconfigure flow.
        """
        if user_input is not None:
            # User acknowledged, close the repair issue
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")


class UnknownIssueRepairFlow(RepairsFlow):
    """Handler for unknown repair issues."""

    def __init__(self, issue_id: str) -> None:
        """Initialize the unknown issue repair flow."""
        super().__init__()
        self._issue_id = issue_id

    async def async_step_init(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        """Handle unknown issues."""
        if user_input is not None:
            # Just acknowledge and close
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="init")
