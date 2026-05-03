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
