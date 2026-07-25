"""Unit tests for outbound-message worker configuration and retry backoff."""

import os
from unittest.mock import patch

from app.config.outbound_message_config import (
    MAX_FAILURE_DETAIL_LENGTH,
    OutboundMessageWorkerConfig,
    compute_retry_delay,
    get_outbound_message_worker_config,
)


def test_max_failure_detail_length_is_a_plain_constant():
    assert MAX_FAILURE_DETAIL_LENGTH == 500


def test_get_outbound_message_worker_config_defaults(monkeypatch):
    for key in (
        "OUTBOUND_MESSAGE_BATCH_SIZE",
        "OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS",
        "OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS",
        "OUTBOUND_MESSAGE_MAX_RETRIES",
        "OUTBOUND_MESSAGE_RETRY_BASE_SECONDS",
        "OUTBOUND_MESSAGE_RETRY_MAX_SECONDS",
        "OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS",
        "OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS",
        "OUTBOUND_MESSAGE_PURGE_INTERVAL_SECONDS",
        "OUTBOUND_MESSAGE_PURGE_BATCH_SIZE",
        "OUTBOUND_MESSAGE_RETRY_JITTER_RATIO",
    ):
        monkeypatch.delenv(key, raising=False)

    config = get_outbound_message_worker_config()

    assert config == OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_retries=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        delivered_retention_days=30,
        failed_retention_days=90,
        purge_interval=3600,
        purge_batch_size=1000,
        retry_jitter_ratio=0.25,
    )


def test_get_outbound_message_worker_config_reads_overrides():
    overrides = {
        "OUTBOUND_MESSAGE_BATCH_SIZE": "25",
        "OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS": "2",
        "OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS": "120",
        "OUTBOUND_MESSAGE_MAX_RETRIES": "3",
        "OUTBOUND_MESSAGE_RETRY_BASE_SECONDS": "30",
        "OUTBOUND_MESSAGE_RETRY_MAX_SECONDS": "600",
        "OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS": "7",
        "OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS": "14",
        "OUTBOUND_MESSAGE_PURGE_INTERVAL_SECONDS": "60",
        "OUTBOUND_MESSAGE_PURGE_BATCH_SIZE": "50",
        "OUTBOUND_MESSAGE_RETRY_JITTER_RATIO": "0",
    }
    with patch.dict(os.environ, overrides):
        config = get_outbound_message_worker_config()

    assert config == OutboundMessageWorkerConfig(
        batch_size=25,
        poll_interval=2,
        lock_timeout=120,
        max_retries=3,
        retry_base_delay=30,
        retry_max_delay=600,
        delivered_retention_days=7,
        failed_retention_days=14,
        purge_interval=60,
        purge_batch_size=50,
        retry_jitter_ratio=0.0,
    )


def test_compute_retry_delay_doubles_per_attempt_and_caps():
    config = OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_retries=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        retry_jitter_ratio=0.0,
        delivered_retention_days=30,
        failed_retention_days=90,
        purge_interval=3600,
        purge_batch_size=1000,
    )

    assert compute_retry_delay(1, config) == 60
    assert compute_retry_delay(2, config) == 120
    assert compute_retry_delay(3, config) == 240
    assert compute_retry_delay(4, config) == 480
    assert compute_retry_delay(10, config) == 3600


def test_compute_retry_delay_applies_bounded_jitter():
    """An SMTP outage fails a whole batch at once; identical delays would retry in lockstep."""

    config = OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_retries=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        retry_jitter_ratio=0.25,
        delivered_retention_days=30,
        failed_retention_days=90,
        purge_interval=3600,
        purge_batch_size=1000,
    )

    delays = {compute_retry_delay(1, config) for _ in range(50)}

    # Never longer than the computed backoff, never shorter than the jitter allows.
    assert all(45 <= delay <= 60 for delay in delays)
    # And genuinely spread, not a constant.
    assert len(delays) > 1


def test_max_attempts_is_the_first_delivery_plus_the_configured_retries():
    config = OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_retries=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        retry_jitter_ratio=0.0,
        delivered_retention_days=30,
        failed_retention_days=90,
        purge_interval=3600,
        purge_batch_size=1000,
    )

    # "Retry at most five times" means one delivery plus five retries.
    assert config.max_attempts == 6
