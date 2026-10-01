import pytest

from app.utils.locale_utils import select_supported_locale


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("en-US", "en-US"),
        ("fr-FR", "fr-FR"),
        ("IT-it", "it-IT"),
        ("fr-CA", "fr-FR"),
        ("it", "it-IT"),
        ("en_GB", "en-US"),
    ],
)
def test_select_supported_locale_matches_exact_and_language_variants(header, expected):
    assert select_supported_locale(header) == expected


def test_select_supported_locale_honors_quality_and_order():
    assert select_supported_locale("fr-FR;q=0.5, it-IT;q=0.9, en-US;q=0.7") == "it-IT"
    assert select_supported_locale("fr-FR, it-IT") == "fr-FR"


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "*",
        "de-DE",
        "fr-FR;q=0",
        "fr-FR;q=invalid",
        "fr-FR;q=1.5",
    ],
)
def test_select_supported_locale_returns_none_without_acceptable_match(header):
    assert select_supported_locale(header) is None


def test_select_supported_locale_skips_malformed_preference_for_later_match():
    assert select_supported_locale("fr-FR;q=invalid, it-IT;q=0.8") == "it-IT"
