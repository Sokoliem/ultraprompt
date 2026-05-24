---
name: "gap-analysis"
description: "**DEFAULT for TARGETED gap analysis on ONE NAMED FEATURE end-to-end (frontend/backend/data/tests/docs): front-door for the gap-analysis cluster: orchestrates feature-completeness-auditor + wiring-gap-inspector and synthesizes confirmed/likely gaps with file:line evidence.** Different from /repo-review (WHOLE-REPO audit, not one feature), /feature-completeness (auditor only, no orchestration), /test-gap-analysis (missing TESTS only), and /dead-code-drift (unused/stale code only). NOT THIS skill if your scope is the whole repo, only the test surface, or only dead code. Triggers: 'gap analysis on <feature>, what's missing in <feature>, end-to-end audit of <feature>, is <feature> done'."
when_to_use: "When the user wants a synthesized gap report across multiple specialists. Triggers on 'gap analysis', 'what's missing', 'find incomplete features', 'where are the wiring gaps', 'merge audit findings into one prioritized list'."
argument-hint: "[optional: feature, workflow, or area to scope the analysis]"
tier: "core"
aliases: ["repo-gaps", "find-gaps", "incomplete-audit"]
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Repo Gap Analysis

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:gap-analysis-lead`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Gap-analysis is multi-agent synthesis across the repo; repo-review is the full audit with map + gaps + readiness; feature-completeness is single-feature deep dive. Use gap-analysis when you have prior auditor findings to merge, OR when starting a focused gap search.

## First signals to inspect

- User has a long list of issues from multiple sources and wants a prioritized merge.
- User asks 'what's incomplete in this repo' without specifying a single feature.
- User wants implementation sequence not just findings.

## Failure modes specific to this lane

- Producing prose narrative instead of structured gap_ledger entries.
- Inventing gaps without upstream auditor evidence.
- Overlapping with /repo-review (which already runs the full panel).
- Failing to assign followup fix-skills to gaps.

## Workflow

1. If no upstream auditor output is in context, dispatch feature-completeness-auditor and wiring-gap-inspector first.
2. Then dispatch gap-analysis-lead with all upstream findings.
3. Synthesis output goes to .ultraprompt/gaps/gap-ledger.jsonl when --write specified.
4. Final report cites evidence per gap; no gap claimed without file:line citation.
5. After synthesis, persist findings to the gap ledger via the `gap_ledger_write` MCP tool: ONE call per gap with required fields (repo, title, category, severity, confidence, evidence, recommended_fix). Auto-skip if --no-ledger argument supplied. Print the gap IDs assigned (e.g., GAP-celestial-0042) for user reference. Before writing, optionally call `gap_ledger_query` with the same repo to detect duplicates from prior sessions — if a similar gap exists, update its evidence rather than create new.
6. Recommend follow-up fix-skills per gap (build, refactor, migrate, test-harden, etc.).

## Validation

Every gap in confirmed_gaps must have evidence with file:line. Every gap in probable_gaps must have an explicit verification_step. Implementation sequence must order phases by dependency, not by severity alone.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Executive summary
    type: section
    required: true
    evidence_rule: "none"
  - field: Confirmed gaps
    type: section
    required: true
    evidence_rule: "none"
  - field: Probable gaps
    type: section
    required: true
    evidence_rule: "none"
  - field: False positives
    type: section
    required: true
    evidence_rule: "none"
  - field: Top 10 risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Quick wins
    type: section
    required: true
    evidence_rule: "none"
  - field: Implementation sequence by phase
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation plan
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Recommended fix-skills per gap
    type: section
    required: true
    evidence_rule: "none"
```

Executive summary | Confirmed gaps (with evidence) | Probable gaps (with verification) | False positives | Top 10 risks | Quick wins | Implementation sequence by phase | Validation plan | Recommended fix-skills per gap

## Subagent delegation

Default: dispatch gap-analysis-lead for synthesis. If no upstream findings exist, first dispatch feature-completeness-auditor + wiring-gap-inspector (parallel via panel-run if requested) and pipe their output.

## V4 aliases

This skill answers to V4 names: `repo-gaps`, `find-gaps`, `incomplete-audit`. The router resolves them to `gap-analysis` and notes the alias in its response.
