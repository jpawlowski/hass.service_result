"""Constants for action_result."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

# Integration metadata
DOMAIN = "action_result"

# Platform parallel updates - applied to all platforms
PARALLEL_UPDATES = 1

# Config entry data keys
CONF_NAME = "name"
CONF_SERVICE_ACTION = "service_action"  # New: stores the action selector result
CONF_SERVICE_DATA_YAML = "service_data_yaml"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RESPONSE_DATA_PATH = "response_data_path"  # JSON path into response data
CONF_ATTRIBUTE_NAME = "attribute_name"  # Custom name for the data attribute
CONF_PARENT_DEVICE = "parent_device"  # Optional: device_id to associate entity with
CONF_ENTITY_CATEGORY = "entity_category"  # Optional: EntityCategory (diagnostic/config/None)

# Sensor type configuration
CONF_SENSOR_TYPE = "sensor_type"  # Type of sensor to create
CONF_VALUE_TYPE = "value_type"  # Data type for value sensor
CONF_UNIT_OF_MEASUREMENT = "unit_of_measurement"  # Unit for value sensor
CONF_UNIT_NUMERATOR = "unit_numerator"  # Numerator for composite unit
CONF_UNIT_DENOMINATOR = "unit_denominator"  # Denominator for composite unit
CONF_DEVICE_CLASS = "device_class"  # Device class for value sensor
CONF_INCLUDE_RESPONSE_DATA = "include_response_data"  # Include full response in attributes
CONF_RESPONSE_DATA_PATH_ATTRIBUTES = "response_data_path_attributes"  # Separate path for attributes in value sensor
CONF_ICON = "icon"  # Custom icon for value sensor

# Enum configuration for text value sensors
CONF_DEFINE_ENUM = "define_enum"  # Whether to define enum values
CONF_ENUM_VALUES = "enum_values"  # List of possible enum values
CONF_ENUM_ICONS = "enum_icons"  # Dict mapping enum values to icons
CONF_ENUM_TRANSLATIONS = "enum_translations"  # Dict[language, Dict[value, translation]]
CONF_ENUM_TRANSLATION_LANGUAGES = "enum_translation_languages"  # List of languages to translate

# Special unit values
UNIT_CUSTOM_COMPOSITE = "__custom_composite__"  # Marker for custom composite unit

# Sensor type values
SENSOR_TYPE_DATA = "data"  # Data sensor with response in attributes (default)
SENSOR_TYPE_VALUE = "value"  # Value sensor with extracted value as state

# Value type options for value sensor
VALUE_TYPE_STRING = "string"
VALUE_TYPE_NUMBER = "number"
VALUE_TYPE_BOOLEAN = "boolean"
VALUE_TYPE_TIMESTAMP = "timestamp"

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
DEFAULT_SENSOR_TYPE = SENSOR_TYPE_DATA
DEFAULT_INCLUDE_RESPONSE_DATA = False  # For value sensors

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

# Repair issue IDs
REPAIR_ISSUE_TRIGGER_ENTITY_MISSING = "trigger_entity_missing"
REPAIR_ISSUE_ENUM_VALUE_ADDED = "enum_value_added"
