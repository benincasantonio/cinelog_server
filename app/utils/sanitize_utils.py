import re


HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_html_tags(value: str) -> str:
    """Strip all HTML tags from a string, preserving the text content."""
    return HTML_TAG_PATTERN.sub("", value).strip()
