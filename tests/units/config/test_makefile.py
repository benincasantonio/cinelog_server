"""Raw-text assertions over the Makefile's outbound-message worker target."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = REPO_ROOT / "Makefile"


def test_makefile_declares_run_email_worker_target():
    makefile = MAKEFILE.read_text()

    assert "run-email-worker:" in makefile
    assert "uv run python -m app.workers.outbound_message_worker" in makefile


def test_makefile_registers_run_email_worker_as_phony():
    makefile = MAKEFILE.read_text()

    phony_line = next(line for line in makefile.splitlines() if line.startswith(".PHONY:"))
    assert "run-email-worker" in phony_line.split()
