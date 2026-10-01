"""Utilities for selecting a supported locale from HTTP language preferences."""

from app.types import LOCALE_CHOICES

_LOCALES_BY_TAG = {locale.casefold(): locale for locale in LOCALE_CHOICES}
_LOCALES_BY_LANGUAGE = {locale.split("-", 1)[0].casefold(): locale for locale in LOCALE_CHOICES}


def _parse_quality(parameters: list[str]) -> float | None:
    """Return the ``q`` weight from an Accept-Language entry's parameters.

    Only the first ``q`` parameter counts, matching the reference parsing
    behavior. Returns None if it's present but malformed or out of range.
    """

    for parameter in parameters:
        if not parameter:
            continue
        name, separator, raw_value = parameter.partition("=")
        if name.strip().casefold() != "q":
            continue
        if not separator:
            return None
        try:
            quality = float(raw_value.strip())
        except ValueError:
            return None
        return quality if 0 <= quality <= 1 else None

    return 1.0


def _parse_preference(position: int, raw_preference: str) -> tuple[float, int, str] | None:
    """Parse one Accept-Language entry into a (quality, position, language_range) triple."""

    parts = [part.strip() for part in raw_preference.split(";")]
    language_range = parts[0]
    if not language_range or language_range == "*":
        return None

    quality = _parse_quality(parts[1:])
    if quality is None or quality <= 0:
        return None

    return quality, position, language_range


def _match_locale(language_range: str) -> str | None:
    """Match a language range against supported locales: exact tag, then primary language."""

    normalized_range = language_range.replace("_", "-").casefold()
    exact_match = _LOCALES_BY_TAG.get(normalized_range)
    if exact_match is not None:
        return exact_match

    primary_language = normalized_range.split("-", 1)[0]
    return _LOCALES_BY_LANGUAGE.get(primary_language)


def select_supported_locale(accept_language: str | None) -> str | None:
    """Return the best supported locale from an ``Accept-Language`` value."""

    if not accept_language:
        return None

    preferences = [
        preference
        for position, raw_preference in enumerate(accept_language.split(","))
        if (preference := _parse_preference(position, raw_preference)) is not None
    ]

    for _, _, language_range in sorted(preferences, key=lambda item: (-item[0], item[1])):
        match = _match_locale(language_range)
        if match is not None:
            return match

    return None
