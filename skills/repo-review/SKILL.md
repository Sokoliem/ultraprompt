---
name: "repo-review"
description: "**DEFAULT for WHOLE-REPO end-to-end audit (map + gaps + drift + test gaps + release readiness in one pass): structured repo review covering map, confirmed gaps, probable gaps, test gaps, contract drift, stale code, release readiness, top risks, quick wins, and implementation sequence — V8 panel-ready.** Different from /gap-analysis (ONE feature end-to-end), /feature-completeness (single feature), /dead-code-drift (drift only), /test-gap-analysis (tests only), /release-readiness (ship/no-ship gate only). Triggers: 'audit the codebase, review the whole repo, what's incomplete across the repo, is this ready to ship overall, comprehensive repo audit'."
when_to_use: "When the user wants a structured whole-repo audit covering map, gaps, contracts, test coverage, drift, and release readiness. Triggers on 'review this repo / what's incomplete / audit the codebase / find what's missing / is this ready to ship / repo health check'."
argument-hint: "[optional: feature or area to focus on]"
tier: "core"
aliases: ["repo-audit", "codebase-review", "repo-health"]
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Repo Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:repo-cartographer` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Repo review is whole-repo audit; review is diff/PR scope; gap-analysis is one feature deep. Use repo-review when the user wants a top-down structured map first, then specialist passes.

## First signals to inspect

- User asks 'is this repo ready' / 'what's missing' / 'audit the codebase'.
- User has just inherited a codebase or is onboarding to one.
- User is preparing for release, security review, or technical due diligence.

## Failure modes specific to this lane

- Producing prose narrative instead of structured artifact.
- Claiming gaps without file-level evidence.
- Overlapping with /review (PR scope) or /architect (architecture scope).
- Running the full specialist panel without user opt-in (cost balloon).

## Workflow

1. Dispatch repo-cartographer first via Task; receive the structured repo map.
2. Identify the 3-5 highest-leverage specialist passes for this repo (offer to dispatch them; do not chain automatically).
3. Synthesize findings into the repo_review_report contract with file-level evidence.
4. Label every gap with confidence (confirmed/likely/possible).
5. End with recommended implementation sequence ordered by risk × effort.

## Validation

Every claim in 'confirmed_gaps' must cite a file path. Every claim in 'probable_gaps' must explain the verification step needed. 'release_readiness' status (ready/risky/blocked) must be backed by at least 3 evidence entries. No generic best-practice findings.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Executive summary
    type: section
    required: true
    evidence_rule: "none"
  - field: Repo map summary
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
  - field: Test gaps
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Contract gaps
    type: section
    required: true
    evidence_rule: "consumer + version + breaking-change classification"
  - field: Stale or dead code
    type: section
    required: true
    evidence_rule: "none"
  - field: Release readiness
    type: section
    required: true
    evidence_rule: "none"
  - field: Top risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Quick wins
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended implementation sequence
    type: section
    required: true
    evidence_rule: "none"
  - field: Validation plan
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
```

Executive summary | Repo map summary | Confirmed gaps (with file evidence) | Probable gaps (with verification steps) | Test gaps (risk-weighted) | Contract gaps | Stale or dead code | Release readiness (ready/risky/blocked) | Top risks | Quick wins | Recommended implementation sequence | Validation plan

## Subagent delegation

Default: dispatch ultraprompt:repo-cartographer for the analysis phase. For deep follow-up specialist passes, recommend (do not auto-chain) the relevant ultraprompt:* agents per gap type. V8 panels: repo-completeness-panel is available for deeper review.

## V4 aliases

This skill answers to V4 names: `repo-audit`, `codebase-review`, `repo-health`. The router resolves them to `repo-review` and notes the alias in its response.
