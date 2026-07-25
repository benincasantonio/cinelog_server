"""Unit tests for the outbound-message worker process module."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from app.workers import outbound_message_worker


@pytest.mark.asyncio
async def test_run_delivery_loop_sleeps_only_after_an_empty_cycle(monkeypatch):
    delivery_service = AsyncMock()
    delivery_service.run_once.side_effect = [3, 0]
    shutdown = asyncio.Event()
    wait_for_calls: list[float] = []

    async def fake_wait_for(awaitable, timeout):
        wait_for_calls.append(timeout)
        awaitable.close()
        shutdown.set()

    monkeypatch.setattr(outbound_message_worker.asyncio, "wait_for", fake_wait_for)

    await outbound_message_worker.run_delivery_loop(delivery_service, shutdown, poll_interval=7)

    assert delivery_service.run_once.await_count == 2
    delivery_service.run_once.assert_any_call(shutdown)
    assert wait_for_calls == [7]


@pytest.mark.asyncio
async def test_run_delivery_loop_survives_a_cycle_exception_and_keeps_polling(monkeypatch):
    delivery_service = AsyncMock()
    delivery_service.run_once.side_effect = [RuntimeError("boom"), 0]
    shutdown = asyncio.Event()
    wait_for_call_count = 0

    async def fake_wait_for(awaitable, timeout):
        nonlocal wait_for_call_count
        awaitable.close()
        wait_for_call_count += 1
        if wait_for_call_count >= 2:
            shutdown.set()

    monkeypatch.setattr(outbound_message_worker.asyncio, "wait_for", fake_wait_for)

    await outbound_message_worker.run_delivery_loop(delivery_service, shutdown, poll_interval=1)

    # Both the failing first cycle and the following empty cycle happened — the
    # exception from the first cycle did not stop the loop from iterating again.
    assert delivery_service.run_once.await_count == 2


@pytest.mark.asyncio
async def test_run_delivery_loop_does_not_run_a_cycle_when_shutdown_is_already_set():
    delivery_service = AsyncMock()
    shutdown = asyncio.Event()
    shutdown.set()

    await outbound_message_worker.run_delivery_loop(delivery_service, shutdown, poll_interval=1)

    delivery_service.run_once.assert_not_awaited()


def test_main_raises_when_email_transport_is_unconfigured(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("SMTP_SERVER", raising=False)

    with pytest.raises(RuntimeError, match="no email transport is configured"):
        outbound_message_worker.main()


@pytest.mark.asyncio
async def test_main_async_raises_before_touching_postgres_when_unconfigured(monkeypatch):
    monkeypatch.setenv("EMAIL_TRANSPORT", "smtp")
    monkeypatch.delenv("SMTP_SERVER", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="no email transport is configured"):
        await outbound_message_worker._main_async()
