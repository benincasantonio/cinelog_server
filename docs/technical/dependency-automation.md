# Dependency Automation

Dependabot uses the `uv` ecosystem at the repository root. It checks Python dependencies weekly and groups version updates into one pull request. `uv` updates both `pyproject.toml` and `uv.lock` when a manifest constraint changes. Security updates remain individual pull requests.

The `uv-lockfile` CI job runs `uv lock --check` to reject a changed manifest with a stale lockfile. Other CI jobs install from the lockfile with `uv sync --frozen --group dev`; frozen sync alone does not check whether the manifest and lockfile match.

Dependabot alerts and repository security updates must be enabled in GitHub settings for automated vulnerability fixes. When changing Dependabot configuration, run **Check for updates** on the default branch and inspect the `uv` job. An update pull request appears only if an update is available.

The Format Dependabot PRs workflow (`.github/workflows/dependabot_format.yml`) runs `make format` on pull requests opened or synchronized by `dependabot[bot]`. That applies Ruff formatting and autofixes with the upgraded lockfile before Code Style checks the branch.

When formatting changes files, the workflow amends Dependabot's existing commit and force-pushes with `--force-with-lease`. Linear Commit History requires exactly one commit, so the workflow does not add a second commit. Same-branch runs queue instead of cancelling an in-progress push. A later Dependabot rebase runs the job again.

Checkout and push use a fine-grained personal access token stored as the Dependabot repository secret `DEPENDABOT_FORMAT_TOKEN`, with contents write on this repository. Dependabot-triggered workflows cannot read Actions secrets, and a push with `GITHUB_TOKEN` would not retrigger Code Style. Create the secret in GitHub under Settings → Secrets and variables → Dependabot. The workflow cannot push until that secret exists.

Lint findings Ruff cannot autofix still fail `make lint`. Review a grouped update's type-check and E2E failures before merging; the tests exercise Uvicorn, PostgreSQL, and Redis while keeping email and TMDB deterministic. See [E2E Testing](e2e-testing.md) and [Code Quality CI](code-quality-ci.md).

## Dependency Auditing

`make dependency-audit` runs `uv run --frozen --group dev pip-audit --strict`. It audits the installed runtime and development dependencies, including transitive dependencies, from `uv.lock`. Frozen mode does not update the lockfile; the separate `uv-lockfile` CI job checks that it matches the manifest. Strict mode also fails when a dependency cannot be collected for auditing. Audit errors must not be suppressed.

The Security Scanning workflow runs this target after installing dependencies on PRs targeting `main`, pushes to `main`, manual runs, and every Monday at 06:23 UTC. The weekly run uses the default branch and detects newly disclosed vulnerabilities without waiting for another code change. It does not create issues, open update PRs, or run `pip-audit --fix`.

Dependabot proposes updates; pip-audit checks whether the installed versions have known vulnerabilities and fails CI if they do. The same advisory may appear in both, but only Dependabot creates automated update PRs. A new advisory can also fail a PR unrelated to dependencies.

### Handling Findings

Read the advisory and its fixed versions, then use `uv lock --upgrade-package PACKAGE==FIXED_VERSION` for a targeted transitive update. Change the manifest as well if a direct dependency constraint prevents the fix. Do not use `pip-audit --fix` to change the installed environment independently of the lockfile.

Run `uv lock --check` and `make dependency-audit` again with no exclusions, followed by the relevant application tests and quality checks. Runtime framework updates require the full unit and E2E suites. An audit service or network failure is a failed check, not evidence that the environment is safe.

### Advisory Exceptions

`PIP_AUDIT_IGNORE_VULNS` is empty by default. It accepts space-separated advisory IDs; the Makefile passes each as a separate `--ignore-vuln` option. For a local investigation, replace the placeholder with the advisory ID:

```bash
make dependency-audit PIP_AUDIT_IGNORE_VULNS="ADVISORY-ID"
```

For an accepted risk, false positive, or vulnerability without an available fix, add the specific ID to `PIP_AUDIT_IGNORE_VULNS` in the Makefile. Each persistent exception must have an adjacent comment explaining why it is accepted, linking to the advisory, and stating the condition for removal. Review the exception when a fix becomes available. No current findings are excluded.

An exception ignores only that advisory, including its aliases; other advisories still fail the audit. Do not disable the audit or suppress its exit code. See the [pip-audit exception documentation](https://github.com/pypa/pip-audit#troubleshooting).

### History

[Issue #86](https://github.com/benincasantonio/cinelog_server/issues/86) removed scheduled scans and automatic issue creation because Dependabot already handled update notifications. The subsequent removal of pip-audit itself in commit `b0f2d8b` has no specific rationale recorded in the issue or PR. [Issue #254](https://github.com/benincasantonio/cinelog_server/issues/254) restores auditing and scheduled checks while leaving update automation to Dependabot.

## See Also

- [Code Quality CI](code-quality-ci.md)
- [E2E Testing](e2e-testing.md)
