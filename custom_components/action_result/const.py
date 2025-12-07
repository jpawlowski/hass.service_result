"""Constants for action_result."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# Integration metadata
DOMAIN = "action_result"
ATTRIBUTION = "Data provided by Home Assistant service calls"

# Platform parallel updates - applied to all platforms
PARALLEL_UPDATES = 1

# Config entry data keys
CONF_NAME = "name"
CONF_SERVICE_ACTION = "service_action"  # New: stores the action selector result
CONF_SERVICE_DATA_YAML = "service_data_yaml"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RESPONSE_DATA_PATH = "response_data_path"  # JSON path into response data
CONF_ATTRIBUTE_NAME = "attribute_name"  # Custom name for the data attribute

# Update mode configuration
CONF_UPDATE_MODE = "update_mode"
CONF_TRIGGER_ENTITY = "trigger_entity"  # Entity to watch for state changes
CONF_TRIGGER_FROM_STATE = "trigger_from_state"  # State to trigger from (optional)
CONF_TRIGGER_TO_STATE = "trigger_to_state"  # State to trigger to (optional)

# Update mode values
UPDATE_MODE_POLLING = "polling"  # Cyclic polling with scan_interval
UPDATE_MODE_MANUAL = "manual"  # Manual trigger via homeassistant.update_entity
UPDATE_MODE_STATE_TRIGGER = "state_trigger"  # Trigger on entity state change

# Legacy config entry data keys (for migration)
CONF_SERVICE_DOMAIN = "service_domain"
CONF_SERVICE_NAME = "service_name"

# Default configuration values
DEFAULT_SCAN_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_ATTRIBUTE_NAME = "data"
DEFAULT_UPDATE_MODE = UPDATE_MODE_POLLING

# Entity state values
STATE_OK = "ok"
STATE_ERROR = "error"
STATE_UNAVAILABLE = "unavailable"
STATE_RETRYING = "retrying"

# Error classification for retry logic
ERROR_TYPE_TEMPORARY = "temporary"  # Retry after backoff
ERROR_TYPE_PERMANENT = "permanent"  # Don't retry, needs user intervention
ERROR_TYPE_UNKNOWN = "unknown"  # Default, treat as temporary

# Retry configuration
MAX_RETRY_COUNT = 3
MAX_CONSECUTIVE_ERRORS = 10  # Cap for exponential backoff calculation
INITIAL_RETRY_DELAY_SECONDS = 30
SERVICE_CALL_TIMEOUT_SECONDS = 30  # Timeout for service calls
MAX_RETRY_DELAY_SECONDS = 300  # 5 minutes max backoff
