---
name: "release"
description: "When user says 'release notes / write changelog / draft release announcement / document this release / what to ship in release notes / what changed in version X' — dispatches writer for structured release notes / changelog artifact. DEFAULT for release communication artifacts. Different from /release-readiness (audits shipability — separate skill)."
when_to_use: "Use for go/no-go assessment, release notes, or changelog drafts. Use `--notes-only` to produce just the notes/changelog without readiness assessment. Do not use mid-development for status updates (use review --summarize)."
argument-hint: "[version|tag|range|--notes-only]"
tier: "core"
aliases: ["release-readiness", "release-notes-changelog", "pr-summarize"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Release

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:writer` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `release-gate-panel`. Preferred: `release-gate-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

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

If readiness: Readiness Checklist | Risk Assessment | Go/No-Go Recommendation | Conditions on Go (if any). If notes: User-Facing Summary | Changelog (grouped) | Migration Guidance | Known Issues.

## Subagent delegation

Use `panel-run release-panel` for parallel readiness/notes/supply-chain assessment. Use `writer` for changelog synthesis from raw commit log.

## V4 aliases

This skill answers to V4 names: `release-readiness`, `release-notes-changelog`, `pr-summarize`. The router resolves them to `release` and notes the alias in its response.
