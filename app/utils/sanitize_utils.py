import re

from app.config.outbound_message_config import MAX_FAILURE_DETAIL_LENGTH

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

NAME_PATTERN = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ '\-]+$")
HANDLE_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_WHITESPACE_PATTERN = re.compile(r"\s+")
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_SENSITIVE_FRAGMENT_PATTERN = re.compile(r"(?i)\b(password|auth)\s*[:=]\s*\S+")


def strip_html_tags(value: str) -> str:
    """Strip all HTML tags from a string, preserving the text content."""
    return HTML_TAG_PATTERN.sub("", value).strip()


def sanitize_failure_detail(value: str, *, max_length: int = MAX_FAILURE_DETAIL_LENGTH) -> str:
    """Sanitize a raw delivery failure message before it is persisted.

    Collapses whitespace, redacts embedded email addresses and
    ``password=``/``auth:``-style credential fragments, then truncates to
    ``max_length``. This is defense in depth — the database CHECK constraint on
    ``outbound_messages.last_error`` is the enforced backstop.
    """

    collapsed = _WHITESPACE_PATTERN.sub(" ", value).strip()
    redacted = _EMAIL_PATTERN.sub("[redacted]", collapsed)
    redacted = _SENSITIVE_FRAGMENT_PATTERN.sub(lambda match: f"{match.group(1)}=[redacted]", redacted)
    return redacted[:max_length]
