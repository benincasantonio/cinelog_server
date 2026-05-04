# Code Quality CI

## Overview

The code quality pipeline runs static checks before changes are merged. The checks are split across focused GitHub Actions workflows so each job can report independently and run in parallel where possible.

## Code Style Workflow

The Code Style workflow is defined in `.github/workflows/code_style.yml` and runs on:

- Pull requests targeting `main`
- Pushes to `main`
- Manual `workflow_dispatch` runs

It has two parallel jobs:

- `lint`: runs `make lint`, which executes `uv run ruff check .`
- `format`: runs `make format-check`, which executes `uv run ruff format --check .`

The format job is check-only and does not modify files in CI.

## Ruff Configuration

Ruff is configured in `pyproject.toml` and is used for both linting and formatting. Black is not required because Ruff formatter owns code formatting for the project.

The configuration targets Python 3.12, uses a 120-character line length, and enables these lint rule families:

- `E`, `W`: pycodestyle errors and warnings
- `F`: Pyflakes checks such as unused imports and undefined names
- `I`: import sorting
- `N`: naming conventions
- `UP`: Python syntax modernization
- `S`: security-oriented checks
- `B`: bug-prone pattern checks
- `A`: builtin shadowing checks
- `C4`: comprehension simplification checks
- `PT`: pytest style checks

Import sorting treats `app` as first-party code.

The lint configuration intentionally ignores a small set of rules that conflict with established project patterns:

- FastAPI route dependencies use `Depends(...)` in default arguments.
- Existing application exception naming uses `AppException`.
- Cookie, token, and test fixture names can look like hardcoded secrets to static analysis.
- Test files use pytest `assert` statements and occasionally broad exception assertions by design.

## Related Workflows

Other quality gates are handled by separate workflows:

- Type checking: `.github/workflows/typecheck.yml`, which runs `make typecheck`
- Security scanning: `.github/workflows/security.yml`, which runs Bandit against `app/`

## Local Usage

Run the same checks locally before opening or updating a pull request:

```bash
make lint
make format-check
make typecheck
make security
```

Use `make format` when local files need to be reformatted or auto-fixed.
