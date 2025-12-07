"""Value type validation for config flow."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from custom_components.action_result.const import (
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_NUMBER,
    VALUE_TYPE_STRING,
    VALUE_TYPE_TIMESTAMP,
)
from homeassistant.util import dt as dt_util


def validate_value_type(
    value: Any,
    value_type: str,
) -> tuple[bool, str | None, Any]:
    """
    Validate that a value can be converted to the specified value type.

    Args:
        value: The value to validate and convert.
        value_type: The target value type (string, number, boolean, timestamp).

    Returns:
        A tuple of (is_valid, error_key, converted_value).
        If valid, returns (True, None, converted_value).
        If invalid, returns (False, error_key, None) where error_key is a translation key.
    """
    if value is None:
        return False, "value_is_none", None

    # String type - everything can be converted to string
    if value_type == VALUE_TYPE_STRING:
        return True, None, str(value)

    # Boolean type
    if value_type == VALUE_TYPE_BOOLEAN:
        # Already a boolean
        if isinstance(value, bool):
            return True, None, value

        # String representation of boolean
        if isinstance(value, str):
            lower_value = value.lower().strip()
            if lower_value in ("true", "yes", "1", "on"):
                return True, None, True
            if lower_value in ("false", "no", "0", "off"):
                return True, None, False
            return False, "value_not_boolean", None

        # Numeric boolean (0 = False, anything else = True)
        if isinstance(value, (int, float)):
            return True, None, bool(value)

        return False, "value_not_boolean", None

    # Number type
    if value_type == VALUE_TYPE_NUMBER:
        # Already a number
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True, None, value

        # String representation of number
        if isinstance(value, str):
            value_str = value.strip()
            try:
                # Try integer first
                if "." not in value_str and "e" not in value_str.lower():
                    return True, None, int(value_str)
                # Otherwise float
                return True, None, float(value_str)
            except ValueError:
                return False, "value_not_number", None

        return False, "value_not_number", None

    # Timestamp type
    if value_type == VALUE_TYPE_TIMESTAMP:
        # Already a datetime
        if isinstance(value, datetime):
            # Ensure timezone-aware datetime
            if value.tzinfo is None:
                # Naive datetime - assume it's in the system's local timezone
                return True, None, dt_util.as_local(value)
            return True, None, value

        # String representation of timestamp
        if isinstance(value, str):
            parsed_dt = dt_util.parse_datetime(value)
            if parsed_dt:
                # Ensure timezone-aware datetime
                if parsed_dt.tzinfo is None:
                    # Naive datetime - assume it's in the system's local timezone
                    parsed_dt = dt_util.as_local(parsed_dt)
                return True, None, parsed_dt
            return False, "value_not_timestamp", None

        # Integer/float as Unix timestamp
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                parsed_dt = dt_util.utc_from_timestamp(value)
            except (ValueError, OSError):
                return False, "value_not_timestamp", None
            else:
                return True, None, parsed_dt

        return False, "value_not_timestamp", None

    # Unknown value type
    return False, "unknown_value_type", None


def convert_value_to_type(value: Any, value_type: str) -> Any:
    """
    Convert a value to the specified value type.

    This function assumes the value has already been validated with validate_value_type().
    It performs the conversion without error checking.

    Args:
        value: The value to convert.
        value_type: The target value type (string, number, boolean, timestamp).

    Returns:
        The converted value, or the original value if conversion is not possible.
    """
    if value is None:
        return None

    # String type
    if value_type == VALUE_TYPE_STRING:
        return str(value)

    # Boolean type
    if value_type == VALUE_TYPE_BOOLEAN:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower().strip() in ("true", "yes", "1", "on")
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(value)

    # Number type
    if value_type == VALUE_TYPE_NUMBER:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            value_str = value.strip()
            try:
                if "." not in value_str and "e" not in value_str.lower():
                    return int(value_str)
                return float(value_str)
            except ValueError:
                return value
        return value

    # Timestamp type
    if value_type == VALUE_TYPE_TIMESTAMP:
        if isinstance(value, datetime):
            # Ensure timezone-aware datetime
            if value.tzinfo is None:
                # Naive datetime - assume it's in the system's local timezone
                return dt_util.as_local(value)
            return value
        if isinstance(value, str):
            parsed_dt = dt_util.parse_datetime(value)
            if parsed_dt:
                # Ensure timezone-aware datetime
                if parsed_dt.tzinfo is None:
                    # Naive datetime - assume it's in the system's local timezone
                    parsed_dt = dt_util.as_local(parsed_dt)
                return parsed_dt
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            try:
                return dt_util.utc_from_timestamp(value)
            except (ValueError, OSError):
                pass
        return value

    return value
