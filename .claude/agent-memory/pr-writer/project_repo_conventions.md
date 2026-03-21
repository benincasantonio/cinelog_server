---
name: repo PR conventions
description: Default branch, commit style, and PR patterns for cinelog_server
type: project
---

Default branch is `main`. Remote is `github.com/benincasantonio/cinelog_server`.

Commit message style uses Conventional Commits with scope: `feat(scope):`, `fix(scope):`, `refactor(scope):`, `chore(scope):`, `docs:`.

PRs are created with `gh pr create` targeting `main`. Branch names follow the pattern `<issue-number>-<short-kebab-description>` (e.g., `100-docs-separate-documentation-into-technical-and-functional-folders`).

Issue references are added both in the PR title context and as `Closes #NNN` in the body.

**Why:** Observed from git log and existing branch/commit naming in the repo.

**How to apply:** Always use Conventional Commits format for PR titles and commit messages. Always include `Closes #NNN` when a GitHub issue number is provided.
