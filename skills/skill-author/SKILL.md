---
name: "skill-author"
description: "When user says 'author a new skill / write a skill / design a skill / new skill for X / skill description / skill spec' — produces a new skill spec with full V8 schema (when_to_use, distinctive_judgment, first_signals, failure_modes, workflow_steps, validation_strategy, output_contract, subagent_delegation). DEFAULT for skill authoring."
when_to_use: "Manual-only. Invoke for new skill authoring or refining an existing skill body. Also handles CLAUDE.md / AGENTS.md / repo guidance file optimization."
argument-hint: "[skill name|target]"
tier: "ecosystem"
aliases: ["skill-authoring", "claude-md-optimize"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Skill Author

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

A good skill is mostly unique specialty content with a single discipline reference. Frontmatter is concise. when_to_use is sharp: when this skill is correct, when adjacent skills are better. Body has consistent shape (Distinctive Judgment | First Signals | Failure Modes | Workflow | Validation | Output Contract | See Also). No inlined boilerplate. Tier assignment matches actual auto-activation desirability.

## First signals to inspect

- Existing skills in the plugin (for shape reference)
- _shared/DISCIPLINE.md (the discipline that skills reference)
- Existing CLAUDE.md or AGENTS.md (for context the skill operates within)
- Adjacent skills that overlap with the new one (for differentiation)
- Aliases needed for backwards compatibility

## Failure modes specific to this lane

- Inlining shared discipline (V4 mistake)
- when_to_use that's vague (matches too many intents)
- Description that doesn't differentiate from adjacent skills
- Body without consistent shape (missing Failure Modes, missing Validation)
- Tier assigned too aggressively (auto-discoverable when manual would be better)
- No alias when renaming (breaks existing users)
- Examples in skill body that are obvious (waste tokens)

## Workflow

1. Confirm the skill is needed (no existing skill covers the lane; not a playbook).
2. Draft frontmatter: name, description, when_to_use, tier, argument-hint.
3. Confirm differentiation from adjacent skills.
4. Draft body with the consistent shape: Distinctive Judgment | First Signals | Failure Modes | Workflow | Validation | Output Contract | See Also.
5. Reference DISCIPLINE.md once; do not inline its contents.
6. Add aliases for any V4 names that should route here.
7. If this is a CLAUDE.md / AGENTS.md update, focus on what makes routing sharper, not on adding more rules.
8. Validate via plugin validator + duplication audit.

## Validation

Run validate-plugin.py and audit-duplication.py. Confirm the skill activates on its target intents (router bench positive case). Confirm it doesn't activate on adjacent intents (router bench negative case).

## Output contract

Skill Frontmatter | Body Sections (with rationale per section) | Aliases Mapped | Tier Justification | Validator + Duplication Audit Result | Router Bench Cases Added (positive + negative)

## Subagent delegation

Dispatch `writer` for body prose synthesis. See `_shared/playbooks/claude-md-template.md` for CLAUDE.md guidance.

## V4 aliases

This skill answers to V4 names: `skill-authoring`, `claude-md-optimize`. The router resolves them to `skill-author` and notes the alias in its response.
