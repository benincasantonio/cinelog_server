"""Outbound-message delivery worker configuration.

Function-getter style of ``app/config/redis.py``: environment variables are read
lazily inside ``get_outbound_message_worker_config()`` rather than at import time.

``MAX_FAILURE_DETAIL_LENGTH`` is imported directly by ``app/models/outbound_message_model.py``
to build its CHECK constraint, so it must stay a plain module-level constant with no
environment dependency — importing the model must never require an environment variable.
"""

import os
from dataclasses import dataclass

MAX_FAILURE_DETAIL_LENGTH = 500


@dataclass(frozen=True)
class OutboundMessageWorkerConfig:
    """Delivery worker tuning parameters."""

    batch_size: int
    poll_interval: int
    lock_timeout: int
    max_attempts: int
    retry_base_delay: int
    retry_max_delay: int


def get_outbound_message_worker_config() -> OutboundMessageWorkerConfig:
    """Return delivery worker configuration from environment variables."""

    return OutboundMessageWorkerConfig(
        batch_size=int(os.getenv("OUTBOUND_MESSAGE_BATCH_SIZE", "10")),
        poll_interval=int(os.getenv("OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS", "5")),
        lock_timeout=int(os.getenv("OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS", "300")),
        max_attempts=int(os.getenv("OUTBOUND_MESSAGE_MAX_ATTEMPTS", "5")),
        retry_base_delay=int(os.getenv("OUTBOUND_MESSAGE_RETRY_BASE_SECONDS", "60")),
        retry_max_delay=int(os.getenv("OUTBOUND_MESSAGE_RETRY_MAX_SECONDS", "3600")),
    )


def compute_retry_delay(attempt_count: int, config: OutboundMessageWorkerConfig) -> int:
    """Return the exponential backoff delay in seconds for a failed attempt.

    ``attempt_count`` is the 1-indexed attempt that just failed — attempt counts are
    incremented at claim time, before delivery is attempted, so a crash mid-send still
    burns an attempt. The delay doubles per attempt (``retry_base_delay * 2**(attempt-1)``)
    and is capped at ``retry_max_delay`` with no jitter, so a persistently failing message
    never waits indefinitely between retries.
    """

    # int.__pow__ is typed to return Any (it can return float for a negative exponent),
    # so pin the intermediate result to int explicitly for mypy's warn_return_any.
    delay: int = config.retry_base_delay * (2 ** (attempt_count - 1))
    return min(delay, config.retry_max_delay)
