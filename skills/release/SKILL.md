---
name: "release"
description: "**DEFAULT for release communication artifacts — dispatches writer for structured release notes and changelog drafting.** Different from /release-readiness (audits whether the codebase is shippable, not the notes), /review (PR-level review, not release-scope), /docs-sync (post-merge doc sync, not release artifact). Triggers: 'release notes, write changelog, draft release announcement, document this release, what to ship in release notes, what changed in version X'."
when_to_use: "Use for go/no-go assessment, release notes, or changelog drafts. Use `--notes-only` to produce just the notes/changelog without readiness assessment. Do not use mid-development for status updates (use review --summarize)."
argument-hint: "[version|tag|range|--notes-only]"
tier: "core"
aliases: ["release-readiness", "release-notes-changelog", "pr-summarize"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Release

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:writer` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Release readiness is a checklist + judgment call. The checklist covers tests, breaking changes, migrations, observability, rollback. The judgment call is whether the residual risk is acceptable. Release notes are user-facing: lead with what changed for users, not what changed in code.

## First signals to inspect

- Tag/version range or commit range to summarize
- git log between last release and HEAD (with --no-merges for cleaner output)
- Changelog file convention (Keep a Changelog, conventional commits, custom)
- Breaking change markers (commits with 'BREAKING' or '!:' or labeled PRs)
- Migration guide or upgrade notes from previous releases (style template)
- CI status, known regressions, open issues tagged for the release

## Failure modes specific to this lane

- Listing every commit in the changelog instead of synthesizing the changes
- Hiding breaking changes in 'Other' section
- Changelog written for developers when the audience is users
- Release readiness 'go' without verifying observability and rollback
- Notes that document broken behavior as intended

## Workflow

1. Identify version/range. List commits and PRs in scope.
2. If `--notes-only`: skip to step 5.
3. Readiness check: tests passing? Breaking changes documented? Migrations rehearsed? Observability in place? Rollback path verified?
4. Risk assessment: what's the residual risk? Acceptable?
5. Group changes by user-facing impact: Breaking, Added, Changed, Deprecated, Removed, Fixed, Security.
6. Write user-facing summary first, then detailed changelog.
7. Include migration guidance for breaking changes.

## Validation

Readiness: confirm CI green, confirm migration tested, confirm observability deployed. Notes: cross-check against actual diff to ensure nothing user-facing is missing.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: If readiness: Readiness Checklist
    type: section
    required: true
    evidence_rule: "none"
  - field: Risk Assessment
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Go/No-Go Recommendation
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
  - field: Conditions on Go
    type: section
    required: true
    evidence_rule: "none"
  - field: Changelog
    type: section
    required: true
    evidence_rule: "none"
  - field: Migration Guidance
    type: section
    required: true
    evidence_rule: "none"
  - field: Known Issues.
    type: section
    required: true
    evidence_rule: "none"
```

If readiness: Readiness Checklist | Risk Assessment | Go/No-Go Recommendation | Conditions on Go (if any). If notes: User-Facing Summary | Changelog (grouped) | Migration Guidance | Known Issues.

## Subagent delegation

Use `panel-run release-panel` for parallel readiness/notes/supply-chain assessment. Use `writer` for changelog synthesis from raw commit log.

## V4 aliases

This skill answers to V4 names: `release-readiness`, `release-notes-changelog`, `pr-summarize`. The router resolves them to `release` and notes the alias in its response.
