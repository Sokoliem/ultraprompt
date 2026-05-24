---
name: "runbook-author"
description: "**DEFAULT for authoring an operational runbook — produces a structured runbook with symptom, severity, verification commands, resolution steps, rollback steps, and escalation paths.** Different from /adr-author (decision record, not operational doc), /docs-sync (documentation drift correction, not runbook authoring), /incident-response (live triage, not the runbook). Triggers: 'write a runbook, on-call playbook, operational doc for X, how to fix Y, escalation path for Z'."
when_to_use: "Use when an on-call engineer needs a step-by-step playbook for a known failure mode. Dispatches writer agent with artifact_type=runbook."
argument-hint: "<symptom|operation>"
tier: "specialist"
aliases: ["on-call-playbook", "operational-doc"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Runbook Author

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

A runbook is for 3 AM. Every step must be copy-pasteable. Verification commands first (is the symptom really happening?), then resolution (fix it), then rollback (in case the fix made things worse), then escalation (who to wake up next).

## First signals to inspect

- Symptom (what does the alert say?)
- Severity (sev-1 wakes someone; sev-3 waits for business hours)
- Existing dashboards / log queries that prove the symptom
- Known fix steps; their failure modes
- Escalation chain

## Failure modes specific to this lane

- Steps that require interpretation ('check if the service looks healthy')
- No verification commands — engineer can't tell if the symptom is real
- No rollback — fix made things worse and there's no undo
- Escalation chain missing or out of date
- Runbook written after the incident with hindsight bias

## Workflow

1. Capture the symptom in user-facing terms.
2. Assign severity per the team's severity scale.
3. List verification commands (with expected output for 'symptom present' vs 'symptom absent').
4. List resolution steps (each copy-pasteable, each idempotent if possible).
5. List rollback steps (in case the fix didn't work).
6. Name escalation contacts.
7. Use _shared/playbooks/runbook-template.md if present.

## Validation

Validate by walking through the runbook as if it were 3 AM and you had never seen the system before. Every step must be unambiguous.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Title + Severity
    type: section
    required: true
    evidence_rule: "none"
  - field: Symptom + How to Verify
    type: section
    required: true
    evidence_rule: "none"
  - field: Resolution Steps
    type: section
    required: true
    evidence_rule: "none"
  - field: Rollback Steps
    type: section
    required: true
    evidence_rule: "none"
  - field: Escalation
    type: section
    required: true
    evidence_rule: "none"
  - field: Related Runbooks
    type: section
    required: true
    evidence_rule: "none"
```

Title + Severity | Symptom + How to Verify | Resolution Steps | Rollback Steps | Escalation | Related Runbooks

## Subagent delegation

Dispatch writer agent with artifact_type=runbook.

## V4 aliases

This skill answers to V4 names: `on-call-playbook`, `operational-doc`. The router resolves them to `runbook-author` and notes the alias in its response.
