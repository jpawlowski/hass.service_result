---
agent: "agent"
tools: ["search/codebase", "edit", "search"]
description: "Add a new service to the integration with proper schema and registration"
---

# Add Service

Your goal is to add a new service to this Home Assistant integration that users can call from automations, scripts, or the UI.

If not provided, ask for:

- Service name and purpose
- Parameters required (with types and validation)
- What the service does (API call, state change, etc.)
- Response data (if any)
- Target: device, entity, or integration-wide

## Implementation Steps

### 1. Define Service in `services.yaml`

**File:** `custom_components/action_result/services.yaml`

Add service definition:

```yaml
[service_name]:
  name: [Human-readable name]
  description: [What the service does]

  # For device or entity-targeted services
  target:
    entity:
      domain: [platform] # sensor, switch, etc.
      # OR
      integration: action_result

  # Service parameters
  fields:
    [parameter_name]:
      name: [Parameter display name]
      description: [What this parameter does]
      required: true # or false
      example: "[example value]"

      # Use selector for better UI
      selector:
        text:
          # OR number:, boolean:, select:, etc.

    [another_parameter]:
      name: [Parameter display name]
      description: [Parameter description]
      required: false
      default: [default value]
      selector:
        number:
          min: 0
          max: 100
          mode: slider
```

### 2. Create Service Handler

**Option A: Simple service in `services/` directory**

Create `custom_components/action_result/services/[service_name].py`:

```python
"""[Service name] service for Action Result Entities."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Service parameter constants
ATTR_PARAMETER = "parameter_name"

# Service schema for validation
SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_PARAMETER): cv.string,
        # Add more parameters with validators
        vol.Optional("optional_param", default=100): cv.positive_int,
    }
)


async def async_setup_service(hass: HomeAssistant) -> None:
    """Set up the [service_name] service."""

    async def async_handle_service(call: ServiceCall) -> None:
        """Handle the service call."""
        # Extract parameters
        parameter_value = call.data[ATTR_PARAMETER]
        optional_value = call.data.get("optional_param", 100)

        _LOGGER.debug(
            "Service [service_name] called with: %s=%s",
            ATTR_PARAMETER,
            parameter_value,
        )

        # Get coordinator or API client from hass.data
        # For each config entry that this service applies to:
        for entry_id, entry_data in hass.data[DOMAIN].items():
            coordinator = entry_data  # Or entry_data["coordinator"]

            try:
                # Perform the service action
                await coordinator.api_client.do_something(parameter_value)

                # Optionally refresh data
                await coordinator.async_request_refresh()

            except Exception as err:
                _LOGGER.error(
                    "Error executing service [service_name]: %s",
                    err,
                )
                # Consider raising HomeAssistantError for user visibility

    # Register the service
    hass.services.async_register(
        DOMAIN,
        "[service_name]",
        async_handle_service,
        schema=SERVICE_SCHEMA,
    )
```

**Option B: Entity-targeted service**

```python
async def async_handle_entity_service(entity, call: ServiceCall) -> None:
    """Handle service call for specific entity."""
    parameter_value = call.data[ATTR_PARAMETER]

    # Entity has access to coordinator
    await entity.coordinator.api_client.do_something(
        entity.device_id,
        parameter_value,
    )
    await entity.coordinator.async_request_refresh()


async def async_setup_service(hass: HomeAssistant) -> None:
    """Set up entity-targeted service."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "[service_name]",
        SERVICE_SCHEMA,
        async_handle_entity_service,
    )
```

### 3. Register Service in `__init__.py`

**File:** `custom_components/action_result/__init__.py`

**CRITICAL:** Services must register in `async_setup` or `setup`, NOT in `async_setup_entry`!

Services are integration-wide, not per config entry.

```python
from .services.[service_name] import async_setup_service as async_setup_[service_name]_service

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    # Register integration-wide services (only once for entire integration)
    await async_setup_[service_name]_service(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    # ... existing setup code ...
    # DO NOT register services here!

    return True
```

**For platform-specific services (entity services):**

Register in platform `__init__.py` during `async_setup_entry`:

```python
# In sensor/__init__.py or other platform
from homeassistant.helpers import entity_platform

async def async_setup_entry(...) -> None:
    """Set up platform."""
    # ... add entities ...

    # Register entity services
    platform = entity_platform.async_get_current_platform()

    from ..services.[service_name] import (
        SERVICE_SCHEMA,
        async_handle_entity_service,
    )

    platform.async_register_entity_service(
        "[service_name]",
        SERVICE_SCHEMA,
        async_handle_entity_service,
    )
```

### 4. Add Service Constants

**File:** `custom_components/action_result/const.py`

```python
# Service names
SERVICE_[SERVICE_NAME] = "[service_name]"

# Service parameters
ATTR_[PARAMETER_NAME] = "[parameter_name]"
```

### 5. Add Translations

**`translations/en.json`:**

```json
{
  "services": {
    "[service_name]": {
      "name": "[Service Name]",
      "description": "[What the service does]",
      "fields": {
        "[parameter_name]": {
          "name": "[Parameter Name]",
          "description": "[Parameter description]"
        }
      }
    }
  }
}
```

**`translations/de.json`:**

```json
{
  "services": {
    "[service_name]": {
      "name": "[German Service Name]",
      "description": "[German description]",
      "fields": {
        "[parameter_name]": {
          "name": "[German Parameter Name]",
          "description": "[German parameter description]"
        }
      }
    }
  }
}
```

### 6. Add Response Data (Optional)

If service returns data:

```python
from homeassistant.core import SupportsResponse

# In service handler
async def async_handle_service(call: ServiceCall) -> dict[str, Any]:
    """Handle service and return data."""
    result = await do_something()

    # Return response data
    return {
        "success": True,
        "value": result,
    }

# When registering
hass.services.async_register(
    DOMAIN,
    "[service_name]",
    async_handle_service,
    schema=SERVICE_SCHEMA,
    supports_response=SupportsResponse.OPTIONAL,  # OPTIONAL: may return data | ONLY: always returns data
)
```

**SupportsResponse values:**

- `NONE` (default): Service does not return data
- `OPTIONAL`: Service may conditionally return data
- `ONLY`: Service always returns data

### 7. Field Filtering by supported_features (Advanced)

For entity services with dynamic fields based on capabilities:

```yaml
# In services.yaml
[service_name]:
  target:
    entity:
      domain: fan
  fields:
    preset_mode:
      # Only show if entity has PRESET_MODE feature
      filter:
        supported_features:
          - fan.FanEntityFeature.PRESET_MODE
      selector:
        select:
          options: [] # Entity provides options dynamically
```

### 8. Service Icons (2025 Best Practice)

Define service icons in `icons.json` instead of hardcoding:

```json
{
  "services": {
    "[service_name]": {
      "service": "mdi:icon-name"
    }
  }
}
```

## Service Types

### Integration-Wide Service

- Applies to all devices/entries
- Example: Refresh all devices, reset cache

### Device-Targeted Service

- Uses `target.device` selector
- Applies to specific device
- Example: Reboot device, update firmware

### Entity-Targeted Service

- Uses `target.entity` selector
- Applies to specific entity
- Example: Set mode, calibrate sensor

## Validation Patterns

### Common Validators

```python
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

SERVICE_SCHEMA = vol.Schema({
    vol.Required("string_param"): cv.string,
    vol.Required("int_param"): cv.positive_int,
    vol.Required("float_param"): vol.Range(min=0.0, max=100.0),
    vol.Required("bool_param"): cv.boolean,
    vol.Required("time_param"): cv.time,
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("enum_param"): vol.In(["option1", "option2", "option3"]),
    vol.Optional("optional_param", default="default"): cv.string,
})
```

### Custom Validator

```python
def validate_custom(value: Any) -> Any:
    """Validate custom parameter."""
    if not meets_criteria(value):
        raise vol.Invalid("Parameter does not meet criteria")
    return value

SERVICE_SCHEMA = vol.Schema({
    vol.Required("custom"): validate_custom,
})
```

## Error Handling

```python
from homeassistant.exceptions import HomeAssistantError

async def async_handle_service(call: ServiceCall) -> None:
    """Handle service with error handling."""
    try:
        result = await do_something(call.data)

    except ConnectionError as err:
        raise HomeAssistantError(
            f"Failed to connect to device: {err}"
        ) from err

    except ValueError as err:
        raise HomeAssistantError(
            f"Invalid parameter value: {err}"
        ) from err
```

## Validation Checklist

- [ ] Service defined in `services.yaml` with proper schema
- [ ] Service handler implemented with error handling
- [ ] Service registered in `async_setup` (integration-wide) or platform `async_setup_entry` (entity service)
- [ ] **CRITICAL:** Integration services NOT registered in `async_setup_entry`
- [ ] Constants added to `const.py`
- [ ] Translations added (en, de)
- [ ] Service icons defined in `icons.json` (optional but recommended)
- [ ] SupportsResponse imported if service returns data
- [ ] Type hints complete
- [ ] Docstrings added
- [ ] `script/check` passes
- [ ] Service appears in HA Developer Tools > Services
- [ ] Service executes correctly
- [ ] Error cases handled appropriately

## Testing

1. Start Home Assistant: `script/develop`
2. Go to Developer Tools > Services
3. Find service: `action_result.[service_name]`
4. Test with valid parameters
5. Test with invalid parameters (should show validation errors)
6. Test with edge cases
7. Check logs for errors

## Integration Context

- **Domain:** `action_result`
- **Services directory:** `custom_components/action_result/services/`
- **Services definition:** `custom_components/action_result/services.yaml`

Follow patterns from existing services in the integration.

## Output

After implementation:

1. Run `script/check` to validate
2. Start Home Assistant and test service
3. Verify service appears in UI with proper description
4. Test all parameters and edge cases
5. Report results
