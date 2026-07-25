"""Process entrypoint for the outbound-message delivery worker.

Mirrors ``main.py``: ``load_dotenv()`` must run before the first ``app`` import, because
``app/__init__.py`` pulls in modules that read environment variables at import time and
raise when they are missing (``JWT_SECRET_KEY``, for example). Running the worker as
``python -m app.workers.outbound_message_worker`` imports the ``app`` package first and
therefore fails before any ``load_dotenv()`` inside that module could help, so the
launcher lives at the repository root instead.

``Dockerfile.prod`` copies this file explicitly alongside ``main.py``.
"""

from dotenv import load_dotenv

load_dotenv()

from app.workers.outbound_message_worker import main  # noqa: E402

if __name__ == "__main__":
    main()
