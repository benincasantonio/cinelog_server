import re


HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ '\-]+$")
HANDLE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def strip_html_tags(value: str) -> str:
    """Strip all HTML tags from a string, preserving the text content."""
    return HTML_TAG_PATTERN.sub("", value).strip()
