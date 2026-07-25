"""Process entrypoint for the outbound-message delivery worker.

Lives under ``app/workers/`` (not ``app/services/``) — everything in this module is a
process concern: signal handling, the poll loop, and logging setup. All delivery logic
lives in ``OutboundMessageDeliveryService``, which this module only calls.

``load_dotenv()`` runs before any ``app.*`` import, mirroring ``alembic/env.py``:
several config modules (e.g. ``app/config/registration_verification_config.py``) read
and raise at import time, so environment variables must already be in place.

This module deliberately never imports ``NotificationService`` or anything from
``app/dependencies/service_dependency.py`` — that import chain requires
``CURSOR_PAGINATION_HMAC_SECRET`` (used only by notification cursor pagination) and the
worker needs no Redis either. It ships in the production image as-is because
``Dockerfile.prod`` already does ``COPY app/ ./app/``.
"""

import asyncio
import contextlib
import logging
import os
import signal

from dotenv import load_dotenv

load_dotenv()

from app.config.outbound_message_config import get_outbound_message_worker_config  # noqa: E402
from app.db.postgres import close_postgres_engine, init_postgres_engine  # noqa: E402
from app.dependencies.repository_dependency import get_outbound_message_repository  # noqa: E402
from app.services.email_service import EmailService  # noqa: E402
from app.services.outbound_message_delivery_service import OutboundMessageDeliveryService  # noqa: E402

logger = logging.getLogger(__name__)


def _install_shutdown_handlers(shutdown: asyncio.Event) -> None:
    """Trigger ``shutdown`` on SIGTERM/SIGINT so the poll loop stops immediately."""

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, shutdown.set)
        except NotImplementedError:
            # add_signal_handler is unavailable on some platforms (e.g. Windows).
            signal.signal(sig, lambda *_args: shutdown.set())


async def run_delivery_loop(
    delivery_service: OutboundMessageDeliveryService,
    shutdown: asyncio.Event,
    *,
    poll_interval: float,
) -> None:
    """Repeatedly run one delivery cycle until ``shutdown`` is set.

    Sleeps only after a cycle that processed nothing — a busy queue is drained back to
    back without an idle wait between batches. The "sleep" waits on the shutdown event
    itself (bounded by ``poll_interval``) rather than a plain ``asyncio.sleep``, so a
    shutdown signal received mid-wait breaks the loop immediately instead of waiting out
    the rest of the interval. A cycle exception is logged and does not kill the loop —
    the next iteration simply tries again.
    """

    while not shutdown.is_set():
        try:
            processed = await delivery_service.run_once(shutdown)
        except Exception:
            logger.exception("Outbound message delivery cycle failed")
            processed = 0

        if processed == 0 and not shutdown.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(shutdown.wait(), timeout=poll_interval)


async def _main_async() -> None:
    email_service = EmailService()
    if not email_service.is_configured():
        raise RuntimeError(
            "Outbound message worker cannot start: no email transport is configured. "
            "Set EMAIL_TRANSPORT=console for local development, or configure SMTP_SERVER."
        )

    config = get_outbound_message_worker_config()
    init_postgres_engine()
    try:
        shutdown = asyncio.Event()
        _install_shutdown_handlers(shutdown)
        delivery_service = OutboundMessageDeliveryService(
            outbound_message_repository=get_outbound_message_repository(),
            email_service=email_service,
            worker_config=config,
        )
        await run_delivery_loop(delivery_service, shutdown, poll_interval=config.poll_interval)
    finally:
        await close_postgres_engine()


def main() -> None:
    """Configure logging and run the worker until it is signaled to stop."""

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
