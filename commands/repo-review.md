---
description: V8. Structured repo review — map, gaps, contracts, test coverage, drift, release readiness. Dispatches repo-cartographer agent for the analysis phase; main thread synthesizes findings.
---

# Repo Review

Run a comprehensive structured audit of the current repository covering:

1. **Repo map** — entrypoints, routes, data models, background jobs, feature flags, CLI surfaces, test commands, deploy surfaces (via `repo-cartographer` agent)
2. **Confirmed gaps** — incomplete features, wiring gaps, contract mismatches with file-level evidence
3. **Probable gaps** — likely issues that need verification
4. **Test gaps** — risk-weighted missing validation
5. **Stale code / drift** — orphaned components, dead code, deprecated patterns
6. **Release readiness** — ship/risky/blocked assessment
7. **Top risks** — what would bite at production scale
8. **Quick wins** — high-value low-effort fixes
9. **Recommended implementation sequence** — ordered fix plan

## Execution

**Dispatch flow:**

1. Dispatch `Task(subagent_type="repo-cartographer", description="Map repo for review", prompt="<context>")` to build the structured repo map first (analysis phase).
2. Main thread synthesizes findings using the repo map; for deep specialist passes (security, performance, contracts, test gaps), recommend additional dispatches but do not chain them automatically — give the user the option.
3. If `$ARGUMENTS` names a specific feature/area, scope the review to that surface.
4. Produce a final report in the structured artifact contract (see `_shared/DISCIPLINE.md` §V8 artifacts).

## Output contract (V8 artifact)

```yaml
repo_review_report:
  executive_summary:
  repo_map_summary:
  confirmed_gaps: []
  probable_gaps: []
  test_gaps: []
  contract_gaps: []
  stale_or_dead_code: []
  release_readiness: # ready | risky | blocked
  top_risks: []
  quick_wins: []
  recommended_sequence: []
  validation_plan: []
```

## V8 note

This is V8 — the repo-completeness pack is available in the V8 release. Specialist agents `feature-completeness-auditor`, `wiring-gap-inspector`, `integration-contract-reviewer`, `test-gap-analyst`, `dead-code-and-drift-hunter`, `release-readiness-auditor`, and `gap-analysis-lead` are available for deeper review passes.
