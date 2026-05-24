---
name: "onboarding-doc"
description: "**DEFAULT for authoring a new-engineer onboarding doc — produces a structured onboarding guide with setup steps, codebase tour, key concepts, common workflows, and a 'first PR' exercise.** Different from /docs-sync (documentation drift correction, not new authoring), /repo-map (machine-readable repo map, not human-facing onboarding), /runbook-author (operational, not onboarding). Triggers: 'onboarding doc, new engineer setup, first day at the repo, codebase tour, getting started, dev environment setup'."
when_to_use: "Use when the team wants a self-serve onboarding guide for new engineers. Dispatches writer agent."
argument-hint: "[target audience: backend|frontend|fullstack|infra]"
tier: "specialist"
aliases: ["new-engineer-guide", "onboarding"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Onboarding Doc

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Onboarding docs decay fast. Lean on existing automation (devcontainer, makefile, Justfile, scripts/) instead of reproducing setup steps that will go stale. The 'first PR exercise' should be a real, mergeable task — not synthetic.

## First signals to inspect

- Existing setup automation (devcontainer.json, Dockerfile.dev, Justfile, scripts/setup.sh)
- Codebase structure (entry points, services, packages)
- Common workflows (run dev server, run tests, deploy)
- Key concepts that aren't obvious from code (auth model, data flow, feature flags)
- Existing onboarding doc (if any) — version it before rewriting

## Failure modes specific to this lane

- Reproducing setup steps the devcontainer / Dockerfile already encodes
- Walls of text the new engineer won't read
- Synthetic 'first PR' that the engineer can't actually merge
- Missing the 'why' for key concepts — engineer learns *what* but not *why*
- Stale links to deprecated docs

## Workflow

1. Inventory existing setup automation; lean on it.
2. Codebase tour: entry points, packages, where to start reading.
3. Key concepts: 3-5 things that aren't obvious from code.
4. Common workflows: run dev, run tests, debug, deploy.
5. First PR exercise: a real, mergeable task at the appropriate scope.
6. Glossary: team-specific terms.

## Validation

Validate by handing the doc to someone who has never seen the repo and having them follow it. Track where they get stuck; iterate.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Audience
    type: section
    required: true
    evidence_rule: "none"
  - field: Setup
    type: section
    required: true
    evidence_rule: "none"
  - field: Codebase Tour
    type: section
    required: true
    evidence_rule: "none"
  - field: Key Concepts
    type: section
    required: true
    evidence_rule: "none"
  - field: Common Workflows
    type: section
    required: true
    evidence_rule: "none"
  - field: First PR Exercise
    type: section
    required: true
    evidence_rule: "none"
  - field: Glossary
    type: section
    required: true
    evidence_rule: "none"
```

Audience | Setup (lean on automation) | Codebase Tour | Key Concepts | Common Workflows | First PR Exercise | Glossary

## Subagent delegation

Dispatch writer agent with artifact_type=onboarding.

## V4 aliases

This skill answers to V4 names: `new-engineer-guide`, `onboarding`. The router resolves them to `onboarding-doc` and notes the alias in its response.
