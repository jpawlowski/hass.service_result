"""
Enum configuration steps.

Contains all steps related to enum configuration for string value sensors:
- async_step_enum_definition: Define enum values
- async_step_enum_icons: Assign icons to enum values
- async_step_enum_translation_languages: Select languages for translations
- async_step_enum_translation: Translate enum values (repeated per language)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from custom_components.action_result.config_flow_handler.schemas import (
    get_enum_definition_schema,
    get_enum_icons_schema,
    get_enum_translation_languages_schema,
    get_enum_translation_schema,
)
from custom_components.action_result.config_flow_handler.steps.helpers import clean_config_data
from custom_components.action_result.const import (
    CONF_DEFINE_ENUM,
    CONF_ENUM_ICONS,
    CONF_ENUM_TRANSLATION_LANGUAGES,
    CONF_ENUM_TRANSLATIONS,
    CONF_ENUM_VALUES,
    CONF_UPDATE_MODE,
)

if TYPE_CHECKING:
    from custom_components.action_result.config_flow_handler.config_flow import ActionResultEntitiesConfigFlowHandler
    from homeassistant import config_entries


async def async_step_enum_definition(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Enum Definition step.

    Offer user to define enum values for text value sensors.
    Only shown when value_type is "string".
    Used by both user flow and reconfigure flow.
    """
    if user_input is not None:
        define_enum = user_input.get(CONF_DEFINE_ENUM, False)

        if define_enum:
            # Parse enum values from comma-separated input
            enum_values_input = user_input.get(CONF_ENUM_VALUES, "")
            enum_values = [v.strip() for v in enum_values_input.split(",") if v.strip()]

            if not enum_values:
                # No values provided - show error and re-display form
                return handler.async_show_form(
                    step_id="enum_definition",
                    data_schema=get_enum_definition_schema(handler._step_data),  # noqa: SLF001
                    errors={"enum_values": "enum_values_required"},
                )

            # Store enum values
            handler._step_data[CONF_DEFINE_ENUM] = True  # noqa: SLF001
            handler._step_data[CONF_ENUM_VALUES] = enum_values  # noqa: SLF001
            # Proceed to enum icons configuration
            return await async_step_enum_icons(handler)

        # User doesn't want enum
        handler._step_data[CONF_DEFINE_ENUM] = False  # noqa: SLF001
        # Clear enum-related fields
        handler._step_data.pop(CONF_ENUM_VALUES, None)  # noqa: SLF001
        handler._step_data.pop(CONF_ENUM_ICONS, None)  # noqa: SLF001
        handler._step_data.pop(CONF_ENUM_TRANSLATIONS, None)  # noqa: SLF001
        handler._step_data.pop(CONF_ENUM_TRANSLATION_LANGUAGES, None)  # noqa: SLF001

        # Check if we're in reconfigure flow
        is_reconfigure = CONF_UPDATE_MODE in handler._step_data and handler._step_data.get(CONF_UPDATE_MODE)  # noqa: SLF001

        if is_reconfigure:
            # Reconfigure flow - update entry and finish
            entry = handler._get_reconfigure_entry()  # noqa: SLF001
            # Clean config data: remove temporary fields and empty values
            cleaned_data = clean_config_data(handler._step_data)  # noqa: SLF001
            return handler.async_update_reload_and_abort(
                entry,
                data=cleaned_data,
            )

        # User flow - proceed to update mode
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_update_mode,
        )

        return await async_step_update_mode(handler)

    return handler.async_show_form(
        step_id="enum_definition",
        data_schema=get_enum_definition_schema(handler._step_data),  # noqa: SLF001
    )


async def async_step_enum_icons(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Enum Icons step.

    Allow user to assign icons to each enum value.
    """
    enum_values = handler._step_data.get(CONF_ENUM_VALUES, [])  # noqa: SLF001

    if user_input is not None:
        # Store icon mappings (filter out empty values)
        enum_icons = {value: icon for value, icon in user_input.items() if icon}
        handler._step_data[CONF_ENUM_ICONS] = enum_icons  # noqa: SLF001
        # Proceed to translation language selection
        return await async_step_enum_translation_languages(handler)

    # Get existing icons if reconfiguring
    existing_data = handler._step_data if handler._step_data else {}  # noqa: SLF001

    return handler.async_show_form(
        step_id="enum_icons",
        data_schema=get_enum_icons_schema(enum_values, existing_data),
    )


async def async_step_enum_translation_languages(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Enum Translation Languages selection step.

    User selects which languages to translate enum values into.
    English is always included.
    """
    if user_input is not None:
        # Store selected languages (always include English)
        selected_languages = user_input.get(CONF_ENUM_TRANSLATION_LANGUAGES, [])
        # Ensure "en" is always first
        all_languages = ["en"] + [lang for lang in selected_languages if lang != "en"]
        handler._step_data[CONF_ENUM_TRANSLATION_LANGUAGES] = all_languages  # noqa: SLF001
        handler._step_data["_current_translation_language_index"] = 0  # Start with English  # noqa: SLF001
        # Proceed to first translation step (English)
        return await async_step_enum_translation(handler)

    return handler.async_show_form(
        step_id="enum_translation_languages",
        data_schema=get_enum_translation_languages_schema(handler._step_data),  # noqa: SLF001
    )


async def async_step_enum_translation(
    handler: ActionResultEntitiesConfigFlowHandler,
    user_input: dict[str, Any] | None = None,
) -> config_entries.ConfigFlowResult:
    """
    Handle Enum Translation step for a specific language.

    This step is dynamically repeated for each selected language.
    Used by both user flow and reconfigure flow.
    """
    languages = handler._step_data.get(CONF_ENUM_TRANSLATION_LANGUAGES, ["en"])  # noqa: SLF001
    current_index = handler._step_data.get("_current_translation_language_index", 0)  # noqa: SLF001
    current_language = languages[current_index]
    enum_values = handler._step_data.get(CONF_ENUM_VALUES, [])  # noqa: SLF001

    if user_input is not None:
        # Store translations for this language
        if CONF_ENUM_TRANSLATIONS not in handler._step_data:  # noqa: SLF001
            handler._step_data[CONF_ENUM_TRANSLATIONS] = {}  # noqa: SLF001
        handler._step_data[CONF_ENUM_TRANSLATIONS][current_language] = user_input  # noqa: SLF001

        # Check if there are more languages to translate
        next_index = current_index + 1
        if next_index < len(languages):
            # Move to next language
            handler._step_data["_current_translation_language_index"] = next_index  # noqa: SLF001
            return await async_step_enum_translation(handler)

        # All translations done - clean up temp data
        handler._step_data.pop("_current_translation_language_index", None)  # noqa: SLF001

        # Check if we're in reconfigure flow
        is_reconfigure = CONF_UPDATE_MODE in handler._step_data and handler._step_data.get(CONF_UPDATE_MODE)  # noqa: SLF001

        if is_reconfigure:
            # Reconfigure flow - update entry and finish
            entry = handler._get_reconfigure_entry()  # noqa: SLF001
            # Clean config data: remove temporary fields and empty values
            cleaned_data = clean_config_data(handler._step_data)  # noqa: SLF001
            return handler.async_update_reload_and_abort(
                entry,
                data=cleaned_data,
            )

        # User flow - proceed to update mode
        from custom_components.action_result.config_flow_handler.steps.update_mode_steps import (  # noqa: PLC0415
            async_step_update_mode,
        )

        return await async_step_update_mode(handler)

    # Display form for current language
    # Get language display name
    language_names = {
        "en": "English",
        "de": "German (Deutsch)",
        "fr": "French (Français)",
        "es": "Spanish (Español)",
        "it": "Italian (Italiano)",
        "nl": "Dutch (Nederlands)",
        "pl": "Polish (Polski)",
        "pt": "Portuguese (Português)",
        "ru": "Russian (Русский)",
        "sv": "Swedish (Svenska)",
        "da": "Danish (Dansk)",
        "nb": "Norwegian (Norsk)",
        "fi": "Finnish (Suomi)",
        "cs": "Czech (Čeština)",
        "sk": "Slovak (Slovenčina)",
        "hu": "Hungarian (Magyar)",
        "ro": "Romanian (Română)",
        "bg": "Bulgarian (Български)",
        "hr": "Croatian (Hrvatski)",
        "sl": "Slovenian (Slovenščina)",
        "el": "Greek (Ελληνικά)",
    }
    language_name = language_names.get(current_language, current_language)

    return handler.async_show_form(
        step_id="enum_translation",
        data_schema=get_enum_translation_schema(current_language, enum_values, handler._step_data),  # noqa: SLF001
        description_placeholders={"language": str(language_name)},
    )
