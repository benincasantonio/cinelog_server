"""Utilities for selecting a supported locale from HTTP language preferences."""

from app.types import LOCALE_CHOICES

_LOCALES_BY_TAG = {locale.casefold(): locale for locale in LOCALE_CHOICES}
_LOCALES_BY_LANGUAGE = {locale.split("-", 1)[0].casefold(): locale for locale in LOCALE_CHOICES}


def select_supported_locale(accept_language: str | None) -> str | None:
    """Return the best supported locale from an ``Accept-Language`` value."""

    if not accept_language:
        return None

    preferences: list[tuple[float, int, str]] = []
    for position, raw_preference in enumerate(accept_language.split(",")):
        parts = [part.strip() for part in raw_preference.split(";")]
        language_range = parts[0]
        if not language_range or language_range == "*":
            continue

        quality = 1.0
        valid = True
        for parameter in parts[1:]:
            if not parameter:
                continue
            name, separator, raw_value = parameter.partition("=")
            if name.strip().casefold() != "q":
                continue
            if not separator:
                valid = False
                break
            try:
                quality = float(raw_value.strip())
            except ValueError:
                valid = False
                break
            if not 0 <= quality <= 1:
                valid = False
            break

        if valid and quality > 0:
            preferences.append((quality, position, language_range))

    for _, _, language_range in sorted(preferences, key=lambda item: (-item[0], item[1])):
        normalized_range = language_range.replace("_", "-").casefold()
        exact_match = _LOCALES_BY_TAG.get(normalized_range)
        if exact_match is not None:
            return exact_match

        primary_language = normalized_range.split("-", 1)[0]
        language_match = _LOCALES_BY_LANGUAGE.get(primary_language)
        if language_match is not None:
            return language_match

    return None
