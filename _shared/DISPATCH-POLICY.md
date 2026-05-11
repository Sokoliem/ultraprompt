# Ultraprompt V8 Shared Dispatch Policy

This file is the canonical reference for V8 skill dispatch behavior. Each skill with `dispatch_to` in its spec references this file rather than embedding the boilerplate. Eliminates ~25% cross-skill duplication.

## Default dispatch behavior

For skills with `dispatch_to` set, the default behavior is:

1. **Dispatch a Task subagent** to the specified `ultraprompt:<agent>` with this skill's discipline as context. Specialist agents run with clean context (no main-thread tool history pollution) and persona-locked system prompts for stronger lane-specific reasoning.

2. **Phase modes:**
   - `phase: full` (default) — entire skill executes via dispatched specialist
   - `phase: analysis` — analysis phase only via specialist; user-confirmed application stays inline

## Task call template

```
Task(
    description="<one-line user intent>",
    subagent_type="ultraprompt:<agent>",
    prompt="""focus: <from $ARGUMENTS or skill default>

<user intent + scope hints + specific files/paths>

Apply discipline at ${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md and the
specialty discipline for the <skill-name> lane (see skill body).
"""
)
```

## Inline override conditions

Stay on the main thread when ALL of these hold:

- The request is genuinely trivial (≤ 5 file reads expected; single concrete question)
- The user explicitly requested an inline answer or fast-path response
- The current main-thread context is already loaded with relevant files

Otherwise: dispatch. Context hygiene is the V8 default; inline is the exception.

## When uncertain

Call `dispatch_advise` MCP tool with the user intent and estimated scope. Returns recommendation (dispatch/inline) + suggested agent + Task brief skeleton.

## Discipline propagation

Whether dispatched or inline, the skill body's specialty discipline applies. The agent reads it from its system prompt; the main thread reads it from this skill's SKILL.md body.
