# GitHub Epic Creation Skill

**Last Updated:** 2026-07-25

## Table of Contents

- [Overview](#overview)
- [Availability and Invocation](#availability-and-invocation)
- [Workflow](#workflow)
- [GitHub Relationships](#github-relationships)
- [Safety and Recovery](#safety-and-recovery)
- [Troubleshooting](#troubleshooting)
- [See Also](#see-also)

## Overview

The `create-github-epic` skill turns a feature brief or prepared ticket list into a GitHub parent
epic, native sub-issues, and blocked-by relationships. It is repository-local and shares one
canonical instruction set across Codex, OpenCode, and Claude Code.

The skill follows the repository's issue-first development flow and existing `[Epic]` convention.
It does not change application behavior, APIs, schemas, or database state.

## Availability and Invocation

| Client | Discovery | Invocation |
|--------|-----------|------------|
| Codex | `.agents/skills/create-github-epic/` | `$create-github-epic` |
| OpenCode | `.agents/skills/create-github-epic/` | Automatic selection or the `skill` tool |
| Claude Code | `.claude/skills/create-github-epic` symlink | `/create-github-epic` |

The canonical `SKILL.md` uses only the common `name` and `description` frontmatter fields.
Codex-specific display metadata lives in `agents/openai.yaml` and is ignored by other clients.

## Workflow

1. Inspect repository instructions, source and documentation context, issue templates, labels,
   milestones, and existing epics.
2. Decompose the requested outcome into independently deliverable children and an acyclic
   dependency graph.
3. Show the complete parent and child bodies, metadata, and Mermaid graph.
4. Wait for explicit approval of that exact manifest.
5. Create the issues, add native relationships, update the parent with actual issue links, and
   verify the live graph.

The parent body lists linked children with ordinary bullets. GitHub's native sub-issue section,
not a duplicated Markdown checklist, tracks child completion.

## GitHub Relationships

Recent GitHub CLI versions support parent and dependency flags directly:

```bash
gh issue create --parent PARENT
gh issue edit DEPENDENT --add-blocked-by BLOCKER
```

The skill checks the installed binary's help before using those flags. This is necessary because
an installed CLI can lag behind the current online manual even when GitHub itself already supports
the relationships.

When native flags are unavailable, the skill uses `gh api` with GitHub's REST endpoints:

- `POST /repos/{owner}/{repo}/issues/{parent}/sub_issues`
- `POST /repos/{owner}/{repo}/issues/{dependent}/dependencies/blocked_by`

These endpoints require the related issue's integer REST `id`, not its issue number or GraphQL
node ID. The skill resolves the ID from the issue's REST resource and verifies relationships with
the corresponding GET endpoints.

## Safety and Recovery

No GitHub write occurs before the user reviews and approves the exact manifest. A material edit
invalidates approval and requires a new preview.

The skill records each created URL and reads relationships before adding them. If a later step
fails, it preserves successful issues, reports the safe resume point, and never deletes or closes
issues as an automatic rollback.

Missing labels, milestones, projects, or issue types are reported rather than created implicitly.
Cross-repository relationships require full issue URLs.

## Troubleshooting

| Problem | Cause | Resolution |
|---------|-------|------------|
| Relationship flags are unknown | Installed `gh` predates the flags | Allow the skill to use its documented `gh api` fallback |
| REST endpoint returns `403` | Token lacks issue write permission | Re-authenticate `gh` with access to the target repository |
| REST endpoint returns `404` | Wrong repository/issue, hidden issue, or unsupported GitHub host | Verify `gh repo view`, issue URLs, host version, and visibility |
| REST endpoint returns `422` | Invalid, cyclic, duplicate, or otherwise rejected relationship | Re-read the live graph; retry only if the intended edge is missing |
| Skill is not visible | Client has not discovered its project skill directory | Restart the client and verify the canonical path or Claude symlink |
| A run stopped after creating some issues | A later issue or relationship write failed | Invoke the skill again; it will rediscover live issues and propose only missing writes |

## See Also

- [Codex skill documentation](https://developers.openai.com/codex/skills/)
- [OpenCode skill documentation](https://opencode.ai/docs/skills/)
- [Claude Code skill documentation](https://code.claude.com/docs/en/skills)
- [GitHub CLI issue manual](https://cli.github.com/manual/gh_issue)
- [GitHub sub-issue REST API](https://docs.github.com/en/rest/issues/sub-issues)
- [GitHub issue dependency REST API](https://docs.github.com/en/rest/issues/issue-dependencies)
