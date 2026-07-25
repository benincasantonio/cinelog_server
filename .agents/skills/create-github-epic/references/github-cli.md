# GitHub CLI Relationship Reference

Use this reference only after the user approves the exact issue manifest.

## Contents

- [Read-only preflight](#read-only-preflight)
- [Capability detection](#capability-detection)
- [Create issues](#create-issues)
- [Native relationship path](#native-relationship-path)
- [REST fallback path](#rest-fallback-path)
- [Idempotency and verification](#idempotency-and-verification)
- [Failure handling](#failure-handling)

## Read-only preflight

Resolve and verify the repository rather than parsing `git remote`:

```bash
repo_slug=$(gh repo view --json nameWithOwner --jq .nameWithOwner)
gh auth status
gh label list --repo "$repo_slug" --limit 200
gh api --paginate "repos/$repo_slug/milestones?state=open&per_page=100"
```

Search both open and closed issues before creating anything:

```bash
gh issue list --repo "$repo_slug" --state all \
  --search '"EXACT TITLE" in:title' \
  --json number,title,state,url
```

Compare returned titles exactly in addition to reviewing near matches.

## Capability detection

Check the installed binary. Online documentation may describe flags that the local binary does
not yet provide.

```bash
if gh issue create --help 2>&1 | grep -q -- '--parent'; then
  native_parent_create=true
else
  native_parent_create=false
fi

if gh issue edit --help 2>&1 | grep -q -- '--add-blocked-by'; then
  native_dependency_edit=true
else
  native_dependency_edit=false
fi
```

Detect parent and dependency support separately. Use the REST fallback for only the unsupported
operation.

## Create issues

Use a body file or standard input. Capture the URL printed by `gh issue create` and derive the
number only after validating that output.

```bash
parent_url=$(gh issue create --repo "$repo_slug" \
  --title "[Epic] EPIC TITLE" \
  --body-file "$parent_body_file" \
  --label enhancement --label feature)
parent_number=${parent_url##*/}
```

Add only labels and milestones that the read-only preflight proved exist. Omit `--milestone`
when no milestone was approved.

## Native relationship path

When supported, link a new child during creation:

```bash
child_url=$(gh issue create --repo "$repo_slug" \
  --title "feat(scope): child title" \
  --body-file "$child_body_file" \
  --parent "$parent_number")
```

For an existing child:

```bash
gh issue edit "$child_number" --repo "$repo_slug" --parent "$parent_number"
```

Add a dependency to the **dependent** issue. This means the dependent cannot finish until the
blocker finishes:

```bash
gh issue edit "$dependent_number" --repo "$repo_slug" \
  --add-blocked-by "$blocker_number"
```

Comma-separate multiple blockers only after every blocker reference is resolved. Prefer full URLs
for cross-repository relationships.

## REST fallback path

All fallback writes still use GitHub CLI through `gh api`.

### Resolve database IDs

The relationship endpoints require the REST integer `id`. Do not pass the GraphQL `node_id` or
the string returned by `gh issue view --json id`.

```bash
child_database_id=$(gh api "repos/$repo_slug/issues/$child_number" --jq .id)
blocker_database_id=$(gh api "repos/$repo_slug/issues/$blocker_number" --jq .id)
```

For a cross-repository issue, resolve the ID from that issue's own `OWNER/REPO`.

### Add a sub-issue

Write to the parent issue and pass the child's database ID:

```bash
gh api --method POST \
  -H "Accept: application/vnd.github+json" \
  "repos/$repo_slug/issues/$parent_number/sub_issues" \
  -F "sub_issue_id=$child_database_id"
```

### Add a blocked-by dependency

Write to the dependent issue and pass the blocker's database ID:

```bash
gh api --method POST \
  -H "Accept: application/vnd.github+json" \
  "repos/$repo_slug/issues/$dependent_number/dependencies/blocked_by" \
  -F "issue_id=$blocker_database_id"
```

Do not replace a failed native relationship with body text. Stop and report when the repository,
GitHub host, or token does not support the relationship endpoint.

## Idempotency and verification

Read before every relationship write:

```bash
gh api --paginate \
  "repos/$repo_slug/issues/$parent_number/sub_issues?per_page=100"

gh api --paginate \
  "repos/$repo_slug/issues/$dependent_number/dependencies/blocked_by?per_page=100"
```

Compare the returned integer `id` or `html_url` with the intended issue. Issue numbers alone are
not unique across repositories.

After all writes, query the same endpoints again and compare the live relationship sets with the
approved manifest. When native JSON fields are available, `gh issue view --json
parent,subIssues,blockedBy,blocking` is an additional check, not a replacement for the
cross-version REST verification.

## Failure handling

- Record each created URL immediately.
- On `401` or `403`, stop and report the missing authentication or permission.
- On `404`, verify host support, repository identity, issue visibility, and endpoint spelling.
- On `409` or `422`, re-read the relationship first; treat it as success only if the intended
  relationship already exists.
- Never delete, close, relabel, or unlink successful partial results as rollback.
- Resume by discovering the parent, children, and live edges, then perform only missing writes
  after a refreshed preview and approval.

## Official references

- [GitHub CLI: create issue](https://cli.github.com/manual/gh_issue_create)
- [GitHub CLI: edit issue](https://cli.github.com/manual/gh_issue_edit)
- [REST API: sub-issues](https://docs.github.com/en/rest/issues/sub-issues)
- [REST API: issue dependencies](https://docs.github.com/en/rest/issues/issue-dependencies)
