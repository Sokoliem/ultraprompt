---
description: Manually dispatch a named Ultraprompt agent with a free-form prompt. Use when dispatch_advise's recommendation is wrong or you want to force a specialist.
argument-hint: "<agent-name> <prompt>"
disable-model-invocation: true
allowed-tools: "Agent, Bash, Read"
---

# Manual Agent Dispatch (V8.9)

Use when you want to force a specific specialist agent rather than relying on
`dispatch_advise` or the V8.7 picker.

## Usage

```
/ultraprompt:dispatch <agent-name> <prompt>
```

Examples:

- `/ultraprompt:dispatch security-auditor "audit auth/ for tenant isolation gaps"`
- `/ultraprompt:dispatch principal-pm "draft a PRD for the new export feature"`
- `/ultraprompt:dispatch reviewer "review the diff on this branch"`

## Workflow

1. Parse `$ARGUMENTS` into `<agent_name>` and `<prompt>`. If empty, print usage and exit.
2. Look up `<agent_name>` in `dist/catalog-metadata.json` `agents[]`. On unknown name, suggest the 3 nearest matches by edit distance and exit.
3. Invoke the Task tool with `subagent_type: <agent_name>` and `prompt: <prompt>`. Pass through `$ARGUMENTS` verbatim — do not paraphrase the user's intent.
4. Write a `dispatch-cmd-invoked` event to the V8 ledger with `{agent, prompt_hash: sha256(prompt), success}`.
5. Surface the agent's structured output back to the user with no rewriting.

## Safety

- `disable-model-invocation: true` — the main thread cannot auto-invoke this; the user must type it.
- Each dispatch is logged; abuse is auditable via `ledger_query --type dispatch-cmd-invoked`.
- Destructive Bash commands run inside the agent still hit the `destructive-command-guard` hook.

## Distinct from peers

- **`/ultraprompt:choose`** — the V8.7 interactive picker when routing is ambiguous. This command is for when you already know which agent you want.
- **`dispatch_advise` MCP tool** — recommends an agent inline. This command actually runs the agent.
- **`/ultraprompt:route`** — read-only routing table. No execution.
