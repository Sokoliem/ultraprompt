---
name: "hooks-design"
description: "**DEFAULT for plugin hook design — dispatches reviewer/architect with plugin hooks focus.**"
when_to_use: "Manual-only. Invoke for hook design, hook auditing, or settings/permissions audit. Hooks are the riskiest plugin surface because they intercept tool calls."
argument-hint: "[hook|surface]"
tier: "ecosystem"
aliases: ["hooks-automation-design", "settings-permissions-audit"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Hooks Design

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Hooks are deterministic guards on tool calls. Three rules: (1) fail open on parse error (a broken hook should not brick the session), (2) provide an env-var disable for emergencies, (3) keep matchers precise (broad matchers create surprises). The evidence ledger is a hook-driven side-effect; the claim gate is an opt-in stop-time check.

## First signals to inspect

- Existing hooks: SessionStart, PreToolUse, PostToolUse, SubagentStart, SubagentStop, Stop, PostToolUseFailure
- Matcher precision (Bash vs Bash|Edit|Write)
- Env var disable mechanism (every hook should respect ULTRAPROMPT_DISABLE_HOOKS=1)
- Fail-open behavior on JSON parse failure
- Evidence ledger integration
- Settings/permissions: who can run what; tool restriction lists

## Failure modes specific to this lane

- Hook crashes on malformed JSON, blocking subsequent tool calls
- Matcher too broad: PostToolUse on `*` instead of `Bash|Edit|Write`
- No env-var disable: user can't override in emergency
- Hook side effects on Stop that confuse the user (extra output)
- Permissions audit that doesn't check defaults (Claude Code's defaults may be permissive)
- Hook script not idempotent (runs twice on retry, breaks state)

## Workflow

1. Identify the hook need: deterministic guard, evidence collection, claim gate.
2. Choose the hook event (PreToolUse, PostToolUse, Stop, etc.) and matcher.
3. Draft the script: parse JSON input safely, fail open on errors, respect disable env var.
4. Wire into hooks.json with timeout.
5. Add fixture test cases (positive, negative, malformed, env-var disabled).
6. For settings/permissions: audit current state, recommend least-privilege defaults.
7. Validate via run-hook-tests.py.

## Validation

Run run-hook-tests.py with the new fixtures. Smoke-test: trigger the hook with intended input (should block/allow as expected). Trigger with malformed input (should not crash session). Set disable env var (should bypass).

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Hook Purpose
    type: section
    required: true
    evidence_rule: "none"
  - field: Event + Matcher
    type: section
    required: true
    evidence_rule: "none"
  - field: Script
    type: section
    required: true
    evidence_rule: "none"
  - field: Fixture Tests Added
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Hooks.json Entry
    type: section
    required: true
    evidence_rule: "none"
  - field: Settings/Permissions Recommendations
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
```

Hook Purpose | Event + Matcher | Script (with fail-open + disable handling) | Fixture Tests Added | Hooks.json Entry | Settings/Permissions Recommendations (if applicable)

## Subagent delegation

Dispatch `auditor` with focus=infra for hook script review. See `_shared/playbooks/settings-permissions-checklist.md`.

## V4 aliases

This skill answers to V4 names: `hooks-automation-design`, `settings-permissions-audit`. The router resolves them to `hooks-design` and notes the alias in its response.
