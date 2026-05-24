---
name: "incident-response"
description: "**DEFAULT for live or post-incident response — produces structured incident timeline, impact assessment, root cause, contributing factors, and an action-item list with owners.** Different from /debug (single-failure root-cause hunt), /postmortem-write (post-incident writeup only, not live response), /review (PR review). Triggers: 'incident, page, outage, postmortem, war room, live triage, sev-1, sev-2'."
when_to_use: "Use when an incident is active or just-resolved and the team needs structured triage + postmortem scaffolding. Dispatches the incident-commander agent."
argument-hint: "<incident-id|description>"
tier: "specialist"
aliases: ["incident-triage", "outage-response", "postmortem-scaffold"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Incident Response

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Live incident work is shaped by time pressure — the structure must be useful in the moment AND survive into postmortem. Lead with current state + blast radius, not history. Use the incident-postmortem-template.md playbook as the artifact skeleton.

## First signals to inspect

- Symptom (what users see, what alerts fired)
- Time started; time-to-detect; time-to-acknowledge
- Affected systems and customer segments
- Current mitigation status
- Available diagnostics (logs, traces, dashboards)

## Failure modes specific to this lane

- Jumping to fixes before agreeing on the symptom
- Conflating symptom, root cause, and contributing factor
- Postmortem with no measurable action items
- Blaming individuals instead of systems
- Skipping the timeline reconstruction

## Workflow

1. Capture current state: symptom, blast radius, mitigation in flight.
2. Reconstruct the timeline: signals → detection → acknowledgement → mitigation → resolution.
3. Distinguish root cause from contributing factors.
4. Draft postmortem scaffold using _shared/playbooks/incident-postmortem-template.md.
5. Action items: each with an owner and a measurable target.
6. Write incident-response artifact to gap_ledger if a structural fix is required.

## Validation

Validate by confirming every action item is measurable and has a named owner. Validate root-cause hypothesis against the timeline; if it doesn't explain when detection started, it's not the root cause.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Symptom + Impact
    type: section
    required: true
    evidence_rule: "none"
  - field: Timeline
    type: section
    required: true
    evidence_rule: "none"
  - field: Mitigation Status
    type: section
    required: true
    evidence_rule: "none"
  - field: Root Cause
    type: section
    required: true
    evidence_rule: "none"
  - field: Contributing Factors
    type: section
    required: true
    evidence_rule: "none"
  - field: Action Items
    type: section
    required: true
    evidence_rule: "none"
  - field: Postmortem Draft Link
    type: section
    required: true
    evidence_rule: "none"
```

Symptom + Impact | Timeline | Mitigation Status | Root Cause | Contributing Factors | Action Items (owner + target) | Postmortem Draft Link

## Subagent delegation

Default: dispatch incident-commander. For deeper technical analysis, follow with /ultraprompt:debug or /ultraprompt:security-audit as appropriate. See _shared/playbooks/incident-postmortem-template.md.

## V4 aliases

This skill answers to V4 names: `incident-triage`, `outage-response`, `postmortem-scaffold`. The router resolves them to `incident-response` and notes the alias in its response.
