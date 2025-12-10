"""
Helper functions for config flow steps.

Shared utilities used across multiple step implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.const import LOGGER
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def extract_action_from_selector(
    action_data: dict[str, Any] | list[dict[str, Any]] | None,
) -> tuple[str, str] | None:
    """
    Extract domain and service name from action selector data.

    The action selector can return data in two formats:
    - Single action: {"action": "domain.service_name", "data": {...}, "target": {...}}
    - Multiple actions (sequence): [{"action": "...", ...}, {"action": "...", ...}]

    Only single actions are supported. If multiple actions are provided, an error is raised.

    Args:
        action_data: The action selector output (dict or list of dicts).

    Returns:
        A tuple of (domain, service_name) or None if invalid.

    Raises:
        ValueError: If multiple actions are provided (not supported).
    """
    if not action_data:
        return None

    # Handle list format (sequence of actions) - reject if multiple
    if isinstance(action_data, list):
        if not action_data:
            return None
        if len(action_data) > 1:
            raise ValueError("Multiple actions are not supported. Please select only one action.")
        action_data = action_data[0]

    # Handle dict format (single action)
    if not isinstance(action_data, dict):
        return None

    action = action_data.get("action", "")
    if not action or "." not in action:
        return None

    parts = action.split(".", 1)
    return (parts[0], parts[1])


async def validate_service_call(
    hass: HomeAssistant,
    domain: str,
    service: str,
    service_data: dict[str, Any],
    target: dict[str, Any] | None = None,
) -> tuple[bool, str | None, str | None]:
    """
    Validate that the service can be called successfully.

    This actually calls the service with return_response=True to verify
    it works before accepting the configuration.

    Args:
        hass: Home Assistant instance.
        domain: Action domain.
        service: Action name.
        service_data: Action data dictionary.
        target: Optional target dictionary (entity_id, device_id, area_id, etc.).

    Returns:
        A tuple of (success, error_key, error_message).
        - success: True if the service call was successful.
        - error_key: Translation key for the error (or None if successful).
        - error_message: The actual error message from the service (or None).
    """
    try:
        response = await hass.services.async_call(
            domain=domain,
            service=service,
            service_data=service_data,
            target=target,
            blocking=True,
            return_response=True,
        )
    except ServiceNotFound:
        return False, "service_not_found", f"Action {domain}.{service} not found"
    except HomeAssistantError as exc:
        error_msg = str(exc)
        LOGGER.warning(
            "Action %s.%s call failed during validation: %s",
            domain,
            service,
            exc,
        )
        return False, "service_call_failed", error_msg
    except Exception as exc:  # noqa: BLE001 - Log unexpected exceptions
        error_msg = str(exc)
        LOGGER.exception(
            "Unexpected error validating service %s.%s",
            domain,
            service,
        )
        return False, "service_call_failed", error_msg
    else:
        # Check if we got a valid response
        if response is None:
            # Action doesn't return data - this is acceptable
            LOGGER.debug(
                "Action %s.%s called successfully (no response data)",
                domain,
                service,
            )
            return True, None, None

        LOGGER.debug(
            "Action %s.%s called successfully, response type: %s",
            domain,
            service,
            type(response).__name__,
        )
        return True, None, None


def get_integration_domain_from_service_action(
    primary_action: dict[str, Any] | list | None,
    fallback_action: dict[str, Any] | list | None = None,
) -> str | None:
    """
    Extract integration domain from service action selector data.

    Tries primary_action first, then falls back to fallback_action if provided.

    Args:
        primary_action: Action selector data to extract domain from (usually from user_input).
        fallback_action: Fallback action selector data (usually from entry.data).

    Returns:
        Integration domain (e.g., "weather", "light") or None if extraction fails.
    """
    LOGGER.debug(
        "Extracting integration domain - primary_action: %s, fallback_action: %s",
        primary_action,
        fallback_action,
    )
    for action_data in [primary_action, fallback_action]:
        if not action_data:
            continue
        try:
            extracted = extract_action_from_selector(action_data)
            if extracted:
                domain = extracted[0]
                LOGGER.debug("Extracted integration domain: %s", domain)
                return domain  # Return domain
        except ValueError:
            # Multiple actions or invalid format - try next source
            LOGGER.debug("Failed to extract domain from action_data: %s", action_data)
            continue
    LOGGER.debug("Could not extract integration domain from any source")
    return None


def clean_config_data(data: dict[str, Any]) -> dict[str, Any]:
    """
    Clean configuration data before saving.

    Removes temporary fields (starting with _) and fields with None values.
    Empty strings are kept for fields where they have semantic meaning (e.g., parent_device).
    This allows default values to be properly applied and keeps the config clean.

    Args:
        data: Configuration data to clean.

    Returns:
        Cleaned configuration data.
    """
    from custom_components.action_result.const import CONF_PARENT_DEVICE  # noqa: PLC0415

    cleaned = {}
    removed_keys = []
    for key, value in data.items():
        # Skip temporary fields (starting with _)
        if key.startswith("_"):
            removed_keys.append(f"{key} (temporary)")
            continue
        # Skip None values
        if value is None:
            removed_keys.append(f"{key} (None)")
            continue
        # Keep empty strings for parent_device (signals 'explicitly cleared')
        if key == CONF_PARENT_DEVICE and value == "":
            cleaned[key] = value
            continue
        # Skip other empty string values
        if value == "":
            removed_keys.append(f"{key} (empty string)")
            continue
        # Keep all other values
        cleaned[key] = value

    if removed_keys:
        LOGGER.debug("clean_config_data: Removed keys: %s", ", ".join(removed_keys))
    LOGGER.debug("clean_config_data: Cleaned data keys: %s", list(cleaned.keys()))
    return cleaned
