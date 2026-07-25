"""Outbound-message delivery worker configuration.

Function-getter style of ``app/config/redis.py``: environment variables are read
lazily inside ``get_outbound_message_worker_config()`` rather than at import time.

``MAX_FAILURE_DETAIL_LENGTH`` is imported directly by ``app/models/outbound_message_model.py``
to build its CHECK constraint, so it must stay a plain module-level constant with no
environment dependency — importing the model must never require an environment variable.
"""

import os
import secrets
from dataclasses import dataclass

MAX_FAILURE_DETAIL_LENGTH = 500


@dataclass(frozen=True)
class OutboundMessageWorkerConfig:
    """Delivery worker tuning parameters."""

    batch_size: int
    poll_interval: int
    lock_timeout: int
    # Retries *after* the first attempt, matching the ticket's "retry at most five
    # times". ``max_attempts`` below converts it to the total the worker counts.
    max_retries: int
    retry_base_delay: int
    retry_max_delay: int
    # Fraction by which a computed backoff may be shortened at random. A batch that
    # fails together on one SMTP outage would otherwise retry in lockstep forever.
    retry_jitter_ratio: float
    # Retention windows. Settled rows keep a recipient address, so they are pruned on a
    # schedule rather than kept forever; terminal failures are kept longer because they
    # are what an operator diagnoses.
    delivered_retention_days: int
    failed_retention_days: int
    # The purge is an unindexed scan over a table holding weeks of history, so it runs
    # on its own schedule rather than before every claim.
    purge_interval: int
    # Rows deleted per purge run, so a long-neglected outbox cannot produce one
    # enormous DELETE holding locks for the whole table.
    purge_batch_size: int

    @property
    def max_attempts(self) -> int:
        """Total attempts allowed: the first delivery plus ``max_retries`` retries."""

        return self.max_retries + 1


def get_outbound_message_worker_config() -> OutboundMessageWorkerConfig:
    """Return delivery worker configuration from environment variables."""

    return OutboundMessageWorkerConfig(
        batch_size=int(os.getenv("OUTBOUND_MESSAGE_BATCH_SIZE", "10")),
        poll_interval=int(os.getenv("OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS", "5")),
        lock_timeout=int(os.getenv("OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS", "300")),
        max_retries=int(os.getenv("OUTBOUND_MESSAGE_MAX_RETRIES", "5")),
        retry_base_delay=int(os.getenv("OUTBOUND_MESSAGE_RETRY_BASE_SECONDS", "60")),
        retry_max_delay=int(os.getenv("OUTBOUND_MESSAGE_RETRY_MAX_SECONDS", "3600")),
        retry_jitter_ratio=float(os.getenv("OUTBOUND_MESSAGE_RETRY_JITTER_RATIO", "0.25")),
        delivered_retention_days=int(os.getenv("OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS", "30")),
        failed_retention_days=int(os.getenv("OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS", "90")),
        purge_interval=int(os.getenv("OUTBOUND_MESSAGE_PURGE_INTERVAL_SECONDS", "3600")),
        purge_batch_size=int(os.getenv("OUTBOUND_MESSAGE_PURGE_BATCH_SIZE", "1000")),
    )


def compute_retry_delay(attempt_count: int, config: OutboundMessageWorkerConfig) -> int:
    """Return the exponential backoff delay in seconds for a failed attempt.

    ``attempt_count`` is the 1-indexed attempt that just failed — attempt counts are
    incremented at claim time, before delivery is attempted, so a crash mid-send still
    burns an attempt. The delay doubles per attempt (``retry_base_delay * 2**(attempt-1)``)
    and is capped at ``retry_max_delay``, so a persistently failing message never waits
    indefinitely between retries.

    The result is then shortened by a random fraction of up to ``retry_jitter_ratio``.
    An SMTP outage fails a whole batch at once, and without jitter every message in it
    would retry in lockstep, re-creating the same thundering herd on every wave.
    ``secrets`` supplies the randomness so the choice is not a weak-PRNG finding; the
    values are not security-sensitive, only spread.
    """

    # int.__pow__ is typed to return Any (it can return float for a negative exponent),
    # so pin the intermediate result to int explicitly for mypy's warn_return_any.
    delay: int = config.retry_base_delay * (2 ** (attempt_count - 1))
    capped = min(delay, config.retry_max_delay)

    spread = int(capped * config.retry_jitter_ratio)
    if spread <= 0:
        return capped
    return capped - secrets.randbelow(spread + 1)
