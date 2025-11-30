"""YAML validation for config flow service data."""

from __future__ import annotations

import yaml


def validate_service_yaml(yaml_string: str) -> tuple[bool, str | None]:
    """
    Validate YAML string for service data.

    Args:
        yaml_string: The YAML string to validate.

    Returns:
        A tuple of (is_valid, error_key).
        If valid, returns (True, None).
        If invalid, returns (False, error_key) where error_key is a translation key.
    """
    if not yaml_string or not yaml_string.strip():
        return True, None

    try:
        parsed = yaml.safe_load(yaml_string)
        if parsed is not None and not isinstance(parsed, dict):
            return False, "yaml_not_dict"
    except yaml.YAMLError:
        return False, "yaml_parse_error"

    return True, None


__all__ = ["validate_service_yaml"]
