"""Raw-text assertions over the Makefile's outbound-message worker target."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = REPO_ROOT / "Makefile"


def test_makefile_declares_run_email_worker_target():
    makefile = MAKEFILE.read_text()

    assert "run-email-worker:" in makefile
    assert "uv run python worker.py" in makefile


def test_makefile_registers_run_email_worker_as_phony():
    makefile = MAKEFILE.read_text()

    phony_line = next(line for line in makefile.splitlines() if line.startswith(".PHONY:"))
    assert "run-email-worker" in phony_line.split()


def test_worker_launcher_loads_dotenv_before_importing_the_app_package():
    """The launcher must live outside ``app`` and load .env before importing it.

    ``python -m app.workers.outbound_message_worker`` imports ``app/__init__.py`` first,
    and several config modules read environment variables at import time, so a
    ``load_dotenv()`` inside the worker module runs far too late.
    """

    launcher = (REPO_ROOT / "worker.py").read_text()

    load_dotenv_position = launcher.index("load_dotenv()")
    app_import_position = launcher.index("from app.workers.outbound_message_worker import main")
    assert load_dotenv_position < app_import_position
    assert "COPY worker.py ./" in (REPO_ROOT / "Dockerfile.prod").read_text()
