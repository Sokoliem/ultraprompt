---
name: "git-workflow"
description: "**DEFAULT for git workflow advice — branching strategy, commit hygiene, merge vs rebase, release branches, hotfix procedure, recovering from bad history.** Different from /review (PR diff review, not workflow), /release (release notes, not branching), /wip-save (snapshot to wip branch, not workflow advice). Triggers: 'branching strategy, merge or rebase, hotfix, release branch, lost a commit, git history, gitflow, trunk based development'."
when_to_use: "Use when the team needs git workflow advice — branching strategy, commit hygiene, history recovery. Inline-only (no agent dispatch); read-only."
argument-hint: "[scenario]"
tier: "specialist"
aliases: ["branching-strategy", "git-strategy"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Git Workflow

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Git workflow is a team-fit problem, not a best-practice problem. Trunk-based fits some teams; release branches fit others. The right answer depends on release cadence, branch protection, and team size. State the choice + the reasoning, not just the recipe.

## First signals to inspect

- Release cadence (daily / weekly / monthly / on-demand)
- Team size and concurrent feature count
- Branch protection rules and review requirements
- Hotfix history (how often, how scoped)
- CI/CD pipeline shape

## Failure modes specific to this lane

- Recommending GitFlow for a team that releases daily
- Recommending trunk-based for a team that needs release branches for compliance
- Step-by-step recipe without the 'why this fits your team' framing
- Ignoring branch protection / review requirements in the recommendation
- Recovery advice that rewrites public history

## Workflow

1. Identify the scenario (branching, merge strategy, recovery, hotfix, release).
2. Capture the team's constraints (cadence, size, compliance, CI shape).
3. Recommend the workflow that fits, with a 'why this and not the alternative' line.
4. For recovery scenarios: identify the non-destructive path first; rewriting history is a last resort.
5. For merge vs rebase: state the tradeoff (clean history vs. provenance).

## Validation

Validate by stating the workflow + the team-fit rationale + the failure mode it avoids. If the recommendation doesn't mention team constraints, it's a recipe, not a workflow.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Scenario
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended Workflow
    type: section
    required: true
    evidence_rule: "none"
  - field: Why This Fits
    type: section
    required: true
    evidence_rule: "none"
  - field: Tradeoffs
    type: section
    required: true
    evidence_rule: "none"
  - field: Step-by-Step
    type: section
    required: true
    evidence_rule: "none"
  - field: What to Avoid
    type: section
    required: true
    evidence_rule: "none"
```

Scenario | Recommended Workflow | Why This Fits | Tradeoffs | Step-by-Step | What to Avoid

## Subagent delegation

None (inline). Pair with /ultraprompt:wip-save for safety before risky operations.

## V4 aliases

This skill answers to V4 names: `branching-strategy`, `git-strategy`. The router resolves them to `git-workflow` and notes the alias in its response.
