---
description: Route a free-form intent to the best Ultraprompt skill or small set of skills using the V8 generated index.
disable-model-invocation: true
argument-hint: <what you want to do>
---

# Route to the best Ultraprompt skill

Route this intent using the V8 generated skill index:

$ARGUMENTS

Preferred path:

1. If the `ultraprompt-meta` MCP server is available, call its `route_intent` tool with the user intent and limit `3`.
2. Otherwise, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/route-intent.py" $ARGUMENTS` (try `python` if `python3` is unavailable).
3. If both fail, use the `ultraprompt:router` subagent as the fallback router.

Return a markdown table with columns: Skill, Confidence, Why, Invoke. Use `/ultraprompt:<name>` for Skill. Confidence is high|medium|low. Invoke is the exact next slash-command including arguments when obvious.

If the intent matches a legacy alias (e.g., `pr-review`, `flake-hunter`), resolve to the canonical skill and note the alias in Why.

If the task is risky enough to warrant independent specialist perspectives, append a one-line note recommending `/ultraprompt:panel-run review-fanout` (or another panel pattern).

Do not implement the task. Only route.
