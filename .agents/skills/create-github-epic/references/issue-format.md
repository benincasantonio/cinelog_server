# Epic and Sub-Issue Format

Use repository-specific templates when they exist. Otherwise apply these structures and adapt
their headings to the repository's established conventions.

## Contents

- [Draft manifest](#draft-manifest)
- [Epic title and body](#epic-title-and-body)
- [Child title and body](#child-title-and-body)
- [Dependency graph](#dependency-graph)
- [Quality rules](#quality-rules)

## Draft manifest

Show the target and write state first:

```markdown
**Repository:** OWNER/REPO
**Write status:** Awaiting explicit approval
**Relationship path:** Native gh flags | gh api fallback
```

Summarize children with stable draft keys:

```markdown
| Key | Title | Labels | Blocked by |
|-----|-------|--------|------------|
| T1 | feat(domain): first capability | feature | — |
| T2 | feat(domain): dependent capability | feature | T1 |
```

Include full parent and child bodies after the table. Do not abbreviate bodies that will be sent
to GitHub.

## Epic title and body

Follow an established repository prefix when one exists. Cinelog uses:

```text
[Epic] Outcome-oriented title
```

Draft the parent with this shape:

```markdown
## Summary

Describe the user or developer outcome and why the grouped work belongs in one epic.

## Agreed behavior and contracts

- State decisions shared by multiple children.
- State compatibility, security, privacy, and API boundaries when relevant.

## Scope

### In scope

- List the capabilities delivered by the epic.

### Out of scope

- List deliberate exclusions that could otherwise be mistaken for omissions.

## Sub-issues and delivery order

- T1 — First independently deliverable outcome.
- T2 — Second outcome; blocked by T1.

Explain which children may proceed in parallel and why dependencies exist.

## Epic acceptance criteria

- [ ] State measurable end-to-end outcomes.
- [ ] Require all native sub-issues to be complete.
- [ ] Include repository quality and documentation requirements.

## Delivery policy

State the repository's issue-branch, review, commit, and pull-request rules.
```

After child creation, replace draft keys in the delivery section with ordinary linked bullets:

```markdown
- #123 — T1: First independently deliverable outcome.
- #124 — T2: Second outcome; blocked by #123.
```

Do not use `- [ ] #123` for the child list. GitHub's native sub-issue relationship owns child
completion state.

## Child title and body

Follow the repository's issue-title convention. Cinelog normally uses Conventional Commit-style
titles such as:

```text
feat(notifications): expose notification preferences
refactor(profile): rename a visibility value
docs(agents): document an agent workflow
```

Draft each child with this shape:

```markdown
## Summary

Describe the independently valuable outcome.

**Parent epic:** #PARENT

## Scope

### In scope

- List concrete behavior, contracts, and affected surfaces.

### Out of scope

- List exclusions and work owned by sibling issues.

## Acceptance criteria

- [ ] Use observable, testable statements.
- [ ] Include failure and compatibility behavior.
- [ ] Include documentation requirements when behavior changes.

## Verification

- Name required unit, integration, end-to-end, migration, or manual checks.

## Implementation constraints

- Preserve repository architecture and explicitly shared epic decisions.
```

The parent reference may appear in the body for human navigation. Keep dependency relationships
native; explain dependency rationale in the epic rather than maintaining a second body-only graph.

## Dependency graph

Use the same edge direction everywhere:

```mermaid
flowchart LR
  T1["T1: Foundation"] --> T2["T2: Dependent capability"]
```

`T1 --> T2` means **T2 is blocked by T1**. Reject a graph containing a path from any node back to
itself. Existing external blockers must use full issue URLs in the manifest.

## Quality rules

- Prefer 3–8 coherent children; use more only when the epic genuinely requires them.
- Avoid children that only add a model, repository, tests, or docs with no independent outcome.
- Give every child unambiguous in-scope and out-of-scope boundaries.
- Put a shared decision in the epic once, then reference it from children.
- Never invent product rules from repository architecture or a related issue. Ask before fixing
  authorization, visibility, uniqueness, deletion, idempotency, pagination, API, or compatibility
  behavior that the user did not specify.
- Mark lower-impact implementation choices as proposals until the manifest is approved.
- Reuse existing labels and milestones; do not invent taxonomy during epic creation.
- Keep each acceptance criterion verifiable without interpreting implementation details.
- Preserve exact approved wording during creation except for replacing draft keys with issue links.
