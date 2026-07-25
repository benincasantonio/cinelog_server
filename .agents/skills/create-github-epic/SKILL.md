---
name: create-github-epic
description: Draft and create GitHub epics with reviewed child issues, native sub-issue links, and blocked-by relationships through GitHub CLI. Use when the user asks to plan, decompose, create, resume, or verify a GitHub epic or a set of linked issues. Always preview the complete manifest and require explicit approval before any GitHub write.
---

# Create GitHub Epic

Create a coherent parent epic and independently deliverable child issues. Treat GitHub's native
sub-issue and dependency relationships as the source of truth.

## Safety boundary

- Perform only read-only repository and GitHub inspection until the preview is approved.
- Never treat skill invocation, a general request to create an epic, or approval of an earlier
  draft as approval of the current manifest.
- Show the exact repository, titles, bodies, labels, milestone, sub-issue links, and dependency
  graph immediately before requesting approval.
- If any material field changes after approval, show the revised manifest and request approval
  again.
- Never create missing labels, milestones, projects, or issue types unless the user separately
  authorizes that mutation.
- Never delete or close partially created issues automatically.
- Follow the repository's `AGENTS.md` and issue workflow in addition to this skill.

## Workflow

### 1. Ground the proposal

Inspect before asking questions:

- Read the applicable `AGENTS.md`, `Makefile`, architecture docs, and relevant source/docs.
- Inspect `.github/ISSUE_TEMPLATE/` and issue forms when present.
- Resolve the repository with `gh repo view`.
- List existing labels, open milestones, and recent or similarly titled epics.
- Search open and closed issues for exact or near-duplicate parent and child titles.
- Inspect one or two representative epics to learn title, body, label, and delivery conventions.

Ask only for product intent or tradeoffs that cannot be derived from these sources.
Repository patterns may establish architecture, naming style, and required quality checks, but they
do not establish new feature behavior. Do not infer visibility, ownership, uniqueness, deletion,
idempotency, pagination, compatibility, endpoint, status-code, or data-retention requirements
from a similar issue or from implementation conventions.

Before drafting, identify every unresolved decision that would materially change the issue graph,
public contract, stored data, authorization boundary, or acceptance criteria. Present concrete
options and a recommended default, then wait for the user's answer. Do not hide assumptions in an
out-of-scope list.

### 2. Decompose the work

- Make every child issue independently reviewable, testable, and valuable.
- Split by delivered behavior or contract rather than by architectural layer alone.
- Put shared decisions and cross-child invariants in the epic.
- Put child-specific scope, acceptance criteria, verification, documentation, and exclusions in
  each child.
- Use only requirements supplied by the user, explicitly documented for the target feature, or
  confirmed during clarification. Label lower-impact implementation details as proposals.
- Express each dependency as: `dependent issue is blocked by blocker issue`.
- Reject self-dependencies and cycles. Do not create issues until the dependency graph is a DAG.
- Use full issue URLs for cross-repository parents or dependencies.

Read [references/issue-format.md](references/issue-format.md) before drafting the manifest.

### 3. Preview the complete manifest

Present, in this order:

1. Target repository and inferred conventions.
2. Epic title, full body, labels, and milestone.
3. A child-issue table with stable draft keys (`T1`, `T2`, ...), title, labels, and blockers.
4. A Mermaid dependency graph where `T1 --> T2` means **T2 is blocked by T1**.
5. Every full child body.
6. The expected relationship strategy: native `gh issue` flags or `gh api` fallback.
7. A concise duplicate-search result.

End with a direct approval request that states the number of issues and target repository. Do not
run any write command until the user approves that exact preview.

### 4. Preflight after approval

- Re-run `gh auth status`, repository resolution, label/milestone validation, and duplicate search.
- Stop if authentication, permissions, repository identity, or requested metadata changed.
- Detect relationship flags from the installed binary's `--help`; never infer support from a
  version number or the online manual.
- Read [references/github-cli.md](references/github-cli.md) before creating or linking issues.
- Keep a creation ledger containing each draft key, created number, URL, and completed
  relationships.

### 5. Create and link

- Create the parent epic first and capture its number and URL.
- Create children in draft-key order. Link the parent during creation when native `--parent` is
  available; otherwise add the native relationship through `gh api`.
- Add dependency relationships only after all same-manifest children exist.
- Before every relationship write, read the current relationships and skip an existing link.
- After all children are known, update the epic's delivery section with ordinary linked bullets.
  Do not duplicate native sub-issues as task-list checkboxes.
- Stream issue bodies through `--body-file` so shell interpolation cannot corrupt Markdown.

### 6. Verify and report

- Re-read the parent, its sub-issues, and every child's `blocked_by` relationships.
- Compare the live graph with the approved manifest by issue database ID or full URL, not just by
  issue number.
- Report the epic URL, a child URL table, verified dependency edges, and the CLI path used.
- If creation stops partway, preserve all created issues. Report the creation ledger, the failed
  command or API response, missing relationships, and exact safe resume point.
- On a resumed run, rediscover existing issues and relationships before proposing any writes.

## Completion requirements

Do not claim success unless:

- Every approved issue exists exactly once.
- Every child is a native sub-issue of the approved parent.
- Every approved blocked-by edge exists and no unapproved edge was added.
- The final epic body contains actual issue links and no duplicate sub-issue task list.
- The user receives all created URLs and any remaining manual action.
