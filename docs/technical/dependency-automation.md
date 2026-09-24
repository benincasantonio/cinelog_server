# Dependency Automation

Dependabot uses the `uv` ecosystem at the repository root. It checks Python dependencies weekly and groups version updates into one pull request. `uv` updates both `pyproject.toml` and `uv.lock` when a manifest constraint changes. Security updates remain individual pull requests.

The `uv-lockfile` CI job runs `uv lock --check` to reject a changed manifest with a stale lockfile. Other CI jobs install from the lockfile with `uv sync --frozen --group dev`; frozen sync alone does not check whether the manifest and lockfile match.

Dependabot alerts and repository security updates must be enabled in GitHub settings for automated vulnerability fixes. When changing Dependabot configuration, run **Check for updates** on the default branch and inspect the `uv` job. An update pull request appears only if an update is available.

If a dependency upgrade changes Ruff formatting, run `make format` on the upgrade branch and include the resulting files in that change. CI only checks formatting. Review a grouped update's type-check and E2E failures before merging; the tests exercise Uvicorn, PostgreSQL, and Redis while keeping email and TMDB deterministic. See [E2E Testing](e2e-testing.md) and [Code Quality CI](code-quality-ci.md).
