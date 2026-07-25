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
        "OUTBOUND_MESSAGE_MAX_ATTEMPTS",
        "OUTBOUND_MESSAGE_RETRY_BASE_SECONDS",
        "OUTBOUND_MESSAGE_RETRY_MAX_SECONDS",
        "OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS",
        "OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS",
    ):
        monkeypatch.delenv(key, raising=False)

    config = get_outbound_message_worker_config()

    assert config == OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_attempts=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        delivered_retention_days=30,
        failed_retention_days=90,
    )


def test_get_outbound_message_worker_config_reads_overrides():
    overrides = {
        "OUTBOUND_MESSAGE_BATCH_SIZE": "25",
        "OUTBOUND_MESSAGE_POLL_INTERVAL_SECONDS": "2",
        "OUTBOUND_MESSAGE_LOCK_TIMEOUT_SECONDS": "120",
        "OUTBOUND_MESSAGE_MAX_ATTEMPTS": "3",
        "OUTBOUND_MESSAGE_RETRY_BASE_SECONDS": "30",
        "OUTBOUND_MESSAGE_RETRY_MAX_SECONDS": "600",
        "OUTBOUND_MESSAGE_DELIVERED_RETENTION_DAYS": "7",
        "OUTBOUND_MESSAGE_FAILED_RETENTION_DAYS": "14",
    }
    with patch.dict(os.environ, overrides):
        config = get_outbound_message_worker_config()

    assert config == OutboundMessageWorkerConfig(
        batch_size=25,
        poll_interval=2,
        lock_timeout=120,
        max_attempts=3,
        retry_base_delay=30,
        retry_max_delay=600,
        delivered_retention_days=7,
        failed_retention_days=14,
    )


def test_compute_retry_delay_doubles_per_attempt_and_caps():
    config = OutboundMessageWorkerConfig(
        batch_size=10,
        poll_interval=5,
        lock_timeout=300,
        max_attempts=5,
        retry_base_delay=60,
        retry_max_delay=3600,
        delivered_retention_days=30,
        failed_retention_days=90,
    )

    assert compute_retry_delay(1, config) == 60
    assert compute_retry_delay(2, config) == 120
    assert compute_retry_delay(3, config) == 240
    assert compute_retry_delay(4, config) == 480
    assert compute_retry_delay(5, config) == 960
    assert compute_retry_delay(10, config) == 3600
