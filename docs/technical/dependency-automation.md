# Dependency Automation

Dependabot uses the `uv` ecosystem at the repository root. It checks Python dependencies weekly and groups version updates into one pull request. `uv` updates both `pyproject.toml` and `uv.lock` when a manifest constraint changes. Security updates remain individual pull requests.

The `uv-lockfile` CI job runs `uv lock --check` to reject a changed manifest with a stale lockfile. Other CI jobs install from the lockfile with `uv sync --frozen --group dev`; frozen sync alone does not check whether the manifest and lockfile match.

Dependabot alerts and repository security updates must be enabled in GitHub settings for automated vulnerability fixes. When changing Dependabot configuration, run **Check for updates** on the default branch and inspect the `uv` job. An update pull request appears only if an update is available.

The Format Dependabot PRs workflow (`.github/workflows/dependabot_format.yml`) runs `make format` on pull requests opened or synchronized by `dependabot[bot]`. That applies Ruff formatting and autofixes with the upgraded lockfile before Code Style checks the branch.

When formatting changes files, the workflow amends Dependabot's existing commit and force-pushes with `--force-with-lease`. Linear Commit History requires exactly one commit, so the workflow does not add a second commit. Same-branch runs queue instead of cancelling an in-progress push. A later Dependabot rebase runs the job again.

Checkout and push use a fine-grained personal access token stored as the Dependabot repository secret `DEPENDABOT_FORMAT_TOKEN`, with contents write on this repository. Dependabot-triggered workflows cannot read Actions secrets, and a push with `GITHUB_TOKEN` would not retrigger Code Style. Create the secret in GitHub under Settings → Secrets and variables → Dependabot. The workflow cannot push until that secret exists.

Lint findings Ruff cannot autofix still fail `make lint`. Review a grouped update's type-check and E2E failures before merging; the tests exercise Uvicorn, PostgreSQL, and Redis while keeping email and TMDB deterministic. See [E2E Testing](e2e-testing.md) and [Code Quality CI](code-quality-ci.md).
