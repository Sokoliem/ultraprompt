---
name: "docs-sync"
description: "**DEFAULT for documentation drift correction: produces documentation update plan + drafts: runs the docs-sync discipline.**"
when_to_use: "Manual-only. Invoke when docs may have drifted from code: stale examples, outdated install instructions, removed flags still documented, screenshots showing old UI. For ADR/design doc creation, see `_shared/playbooks/adr-template.md` and `_shared/playbooks/design-doc-template.md`."
argument-hint: "[doc|surface|version range]"
tier: "specialist"
aliases: ["docs-sync"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Docs Sync

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Documentation drift is silent: nothing fails when README says `npm install` but the project moved to pnpm. Find drift by cross-checking docs against code reality: install commands against package manager, examples against current API, flags against current CLI, screenshots against current UI. Fix the docs; do not fix the code to match the docs (unless the code is wrong).

## First signals to inspect

- README install + quickstart commands vs actual package manager / scripts
- Code examples in docs vs current API
- CLI flag documentation vs current flags (--help output)
- Configuration examples vs current config schema
- Architecture diagrams vs current code structure
- Changelog gaps (releases without notes)
- Doc comments vs current function signatures

## Failure modes specific to this lane

- Documenting broken behavior as intended behavior
- Updating docs without confirming the new behavior actually works
- Adding 'TODO: update' instead of updating
- Removing examples instead of fixing them
- Fixing the code to match wrong docs (docs were aspirational, not specification)

## Workflow

1. Inventory docs in scope: README, /docs, examples, code comments, changelog.
2. Cross-check each against code reality.
3. For each drift: classify as (a) docs wrong, fix docs; (b) code wrong, surface as a finding for separate fix; (c) docs aspirational, decide.
4. Update docs. Run examples to confirm they work.
5. Update changelog if release-relevant.
6. Validate by running quickstart + examples end-to-end.

## Validation

Run install + quickstart from scratch (clean checkout). Run every code example. Verify CLI help matches documented flags. Verify config schema matches documented config.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Docs Inventory
    type: section
    required: true
    evidence_rule: "none"
  - field: Drift Found
    type: section
    required: true
    evidence_rule: "none"
  - field: Fixes Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Code-Wrong Findings
    type: section
    required: true
    evidence_rule: "file:line citation + severity + confidence label"
  - field: Validation: Quickstart Run
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Validation: Examples Run
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Remaining Drift
    type: section
    required: true
    evidence_rule: "none"
```

Docs Inventory | Drift Found | Fixes Applied (per file) | Code-Wrong Findings (separate fix) | Validation: Quickstart Run | Validation: Examples Run | Remaining Drift

## Subagent delegation

Dispatch `writer` for changelog synthesis from raw commit log. See `_shared/playbooks/release-notes-format.md`.

## V4 aliases

This skill answers to V4 names: `docs-sync`. The router resolves them to `docs-sync` and notes the alias in its response.
