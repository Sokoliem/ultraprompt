---
name: "repo-review"
description: "When user says 'review this whole repo / what's incomplete / audit the codebase end-to-end / what gaps exist / find what's missing / is this ready to ship' — produces a structured repo review covering map (entrypoints, routes, data, jobs), confirmed gaps, probable gaps, test gaps, contract drift, stale code, release readiness, top risks, quick wins, and implementation sequence. DEFAULT for any whole-repo audit prompt. V8 panel-ready skill."
when_to_use: "When the user wants a structured whole-repo audit covering map, gaps, contracts, test coverage, drift, and release readiness. Triggers on 'review this repo / what's incomplete / audit the codebase / find what's missing / is this ready to ship / repo health check'."
argument-hint: "[optional: feature or area to focus on]"
tier: "core"
aliases: ["repo-audit", "codebase-review", "repo-health"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Repo Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:repo-cartographer` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `repo-completeness-panel`. Preferred: `repo-completeness-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

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

Executive summary | Repo map summary | Confirmed gaps (with file evidence) | Probable gaps (with verification steps) | Test gaps (risk-weighted) | Contract gaps | Stale or dead code | Release readiness (ready/risky/blocked) | Top risks | Quick wins | Recommended implementation sequence | Validation plan

## Subagent delegation

Default: dispatch ultraprompt:repo-cartographer for the analysis phase. For deep follow-up specialist passes, recommend (do not auto-chain) the relevant ultraprompt:* agents per gap type. V8 panels: repo-completeness-panel is available for deeper review.

## V4 aliases

This skill answers to V4 names: `repo-audit`, `codebase-review`, `repo-health`. The router resolves them to `repo-review` and notes the alias in its response.
