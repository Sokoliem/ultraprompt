---
name: "adr-author"
description: "**DEFAULT for authoring an Architecture Decision Record — produces a structured ADR with context, decision drivers, considered options, decision, consequences, and status, using the adr-template.md playbook.** Different from /architect (architecture exploration, not the record), /prd-technical (forward-looking product spec, not a decision record), /writer (general technical writing, not ADR-specific). Triggers: 'write an ADR, document this decision, decision record, ADR for X, architecture decision'."
when_to_use: "Use when an architectural decision has been made and needs to be recorded for posterity. Dispatches the writer agent with ADR artifact_type."
argument-hint: "<decision title|short description>"
tier: "specialist"
aliases: ["architecture-decision", "decision-record"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# ADR Author

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

An ADR is a contract with future engineers. It must: name the decision, name alternatives that were considered (not strawmen), name the consequences (good and bad), and have a status that updates as the decision evolves (proposed/accepted/superseded).

## First signals to inspect

- What decision is being made
- Who needs to know (engineering, product, ops)
- Existing ADR conventions in the repo (numbering, location, status lifecycle)
- Constraints that drove the decision
- Alternatives that were genuinely considered

## Failure modes specific to this lane

- Strawmen alternatives that were never seriously considered
- No consequences section, or consequences-without-bad
- Status missing or wrong (e.g., 'accepted' when not yet implemented)
- Decision drivers list missing — readers can't tell why
- Authored after the fact with hindsight bias

## Workflow

1. Identify the decision and its scope.
2. List the decision drivers (constraints, requirements, forces).
3. Enumerate considered options. Strawmen don't count.
4. State the decision and the rationale.
5. Spell out consequences (good and bad, near-term and long-term).
6. Set status (proposed / accepted / superseded).
7. Use _shared/playbooks/adr-template.md as the skeleton.

## Validation

Validate by reading the ADR back as a stranger: does it explain *why* this decision was made, what the alternatives were, and what could go wrong? If not, it's not an ADR.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Title + Status + Date
    type: section
    required: true
    evidence_rule: "none"
  - field: Context
    type: section
    required: true
    evidence_rule: "none"
  - field: Decision Drivers
    type: section
    required: true
    evidence_rule: "none"
  - field: Considered Options
    type: section
    required: true
    evidence_rule: "none"
  - field: Decision
    type: section
    required: true
    evidence_rule: "none"
  - field: Consequences
    type: section
    required: true
    evidence_rule: "none"
  - field: Supersedes / Superseded by
    type: section
    required: true
    evidence_rule: "none"
```

Title + Status + Date | Context | Decision Drivers | Considered Options | Decision | Consequences (good/bad) | Supersedes / Superseded by (if applicable)

## Subagent delegation

Dispatch writer agent with artifact_type=adr. See _shared/playbooks/adr-template.md.

## V4 aliases

This skill answers to V4 names: `architecture-decision`, `decision-record`. The router resolves them to `adr-author` and notes the alias in its response.
