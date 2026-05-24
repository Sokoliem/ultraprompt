---
name: "problem-framing"
description: "**DEFAULT for problem-framing decisions — produces structured problem reframings (jobs-to-be-done, constraints, customer segment, substitutes, time horizon lenses) with explicit implications.** Different from /idea-triage (ranks ideas, not frames problems), /concept-brief (after problem is framed), /innovation-lead (idea generation)."
when_to_use: "When the user has a problem statement but suspects it might be framed wrong, or wants to explore alternative framings before locking in a direction. Critical pre-PRD step if problem framing affects what to build."
argument-hint: "<problem statement or topic>"
tier: "core"
aliases: ["reframe-problem", "problem-statement", "job-framing"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Problem Framing

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:innovation-lead`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Problem-framing reframes a known problem; opportunity-map explores opportunity space; idea-triage ranks existing ideas; concept-brief drafts a chosen concept. Use problem-framing when you suspect you're about to solve the wrong problem.

## First signals to inspect

- User has a problem statement but isn't confident it's right.
- User says 'the real problem is...' or 'we're framing this as...'.
- Pre-PRD stage where framing decisions are still open.

## Failure modes specific to this lane

- Producing only one reframing (the value is in alternatives).
- Skipping the implications per reframing.
- Missing 'what this framing excludes' (every framing has scope it rules out).
- Endless reframings without a recommended framing.
- Ignoring customer signals that already constrain the framing.

## Workflow

1. Dispatch innovation-lead for problem framing with multiple lenses.
2. Produce 3-5 alternative framings using different lenses (jobs-to-be-done, constraints, customer segment, substitutes, time horizon).
3. For each framing: state the rephrased problem + implications for what we'd build.
4. Recommended framing with reasoning.
5. Each framing names what it excludes (scope it rules out).
6. End with the recommended framing + open questions about it.

## Validation

Minimum 3 reframings produced. Each names its lens. Each has explicit implications. Each names what it excludes. Recommended framing has reasoning.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Original problem statement
    type: section
    required: true
    evidence_rule: "none"
  - field: 3-5 reframings
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended framing with reasoning
    type: section
    required: true
    evidence_rule: "none"
  - field: Key assumptions in recommended framing
    type: section
    required: true
    evidence_rule: "none"
  - field: Open questions
    type: section
    required: true
    evidence_rule: "none"
```

Original problem statement | 3-5 reframings (with lens + rephrased problem + implications + what-it-excludes) | Recommended framing with reasoning | Key assumptions in recommended framing | Open questions

## Subagent delegation

Default: dispatch innovation-lead. Chain customer-advocate if customer signals available. Followup: concept-brief or prd-lite for the chosen framing.

## V4 aliases

This skill answers to V4 names: `reframe-problem`, `problem-statement`, `job-framing`. The router resolves them to `problem-framing` and notes the alias in its response.
