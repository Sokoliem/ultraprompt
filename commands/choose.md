---
description: "V8.7 interactive routing picker. Surfaces top skill candidates + 2 LLM-rewritten prompt variants via AskUserQuestion, then dispatches the chosen skill with the chosen phrasing."
argument-hint: "<original prompt / intent>"
---

# Ultraprompt Choose (Interactive Picker)

Invoke the `ultraprompt:choose` Skill with the user's intent as the argument:

$ARGUMENTS

The Skill body owns the orchestration — it calls the `route_picker` MCP tool (which returns ranked candidates with previews and ambiguity metadata), generates 2 LLM-rewritten prompt variants and routes each via `route_intent`, then surfaces a 3-4 option `AskUserQuestion` with side-by-side previews. On user selection, the Skill dispatches the chosen downstream Skill with the chosen phrasing — or, if the chosen Skill is `manual_only`, surfaces the slash command for the user to run.

Use this instead of `/ultraprompt:route` when you want an interactive selection moment rather than a read-only table.

If `$ARGUMENTS` is empty, ask the user for their intent before invoking the Skill.
