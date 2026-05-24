---
name: "choose"
description: "**DEFAULT for ROUTING AMBIGUITY — interactive picker that surfaces top skill candidates + 2 LLM-rewritten prompt variants via AskUserQuestion with previews, then dispatches the chosen skill with the chosen phrasing: AskUserQuestion-driven selection moment when the V8 router can't decide; on choice, dispatches the picked skill (or surfaces the slash command for manual_only skills) and logs the choice for the learning queue.** Different from /route (read-only routing table — this is interactive picker), /menu (catalog browser — this is scoped to the current prompt), /pathfind (workflow path across multiple skills — this picks ONE skill). Triggers: 'auto-invoked by the V8.7 UserPromptSubmit hook when top-2 skills are within 15% or top is medium confidence; manually invokable as /ultraprompt:choose <intent>'."
when_to_use: "Use when routing is ambiguous (top-2 skills within ~15% of each other), when the prompt is vague, when the user wants to pick between near-equal options, or whenever the model needs the user to disambiguate before doing work. Auto-invoked by the V8.7 UserPromptSubmit hook directive when ambiguity is detected; also invocable manually via `/ultraprompt:choose <intent>`."
argument-hint: "<original prompt / intent>"
tier: "core"
aliases: ["pick", "route-interactive"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Choose

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Interactive arbitration. Take the user's free-form intent, surface top skill candidates plus 2 LLM-rewritten prompt variants paired with their best-matching skills, present them via AskUserQuestion with previews, and dispatch the chosen skill with the chosen phrasing. The goal is one decisive selection moment instead of a wrong-skill output that has to be redone.

## First signals to inspect

- User's prompt (passed as `$ARGUMENTS` or carried in the hook directive)
- Inline `candidates` JSON from the hook directive (if present, skip the `route_picker` call)
- `route_picker` MCP tool output: top-N candidates with previews + ambiguity metadata
- Per-rewrite `route_intent` MCP calls to find the best skill for each rewritten phrasing

## Failure modes specific to this lane

- Surfacing the same skill twice across options (dedupe by skill name before building AskUserQuestion)
- Forcing the picker on an already-unambiguous prompt — only run when the hook directive fires or the user invokes manually
- Generating rewrites that route to the SAME top skill as the original — skip those rewrites
- More than 4 options — AskUserQuestion supports max 4 (plus auto Other); cap at 4
- Picking a `manual_only` skill and trying to dispatch it via Skill tool — instead, instruct the user to run the slash command
- Skipping the dispatch after the user picks — the picker is not a report; it must follow through and invoke

## Workflow

1. Resolve the user's prompt from `$ARGUMENTS` or the inline directive payload. If the hook supplied inline `candidates`, use them directly and skip step 2.
2. Otherwise call MCP tool `route_picker` with `{intent: <prompt>, top_n: 3, include_previews: true}` to get ranked candidates with previews and ambiguity metadata.
3. Generate 2 alternative phrasings of the user's prompt that (a) make the intent more concrete and (b) would route to a different skill than the top candidate. For each rewrite, call `route_intent` with `{intent: <rewrite>, limit: 1}` to find its best skill. Discard any rewrite whose top skill equals the original top.
4. Build an `AskUserQuestion` with up to 4 options: Option A = top candidate + original prompt; Option B = 2nd candidate + original prompt; Options C/D = each rewrite + its best-match skill. Populate the `preview` field of each option with the skill's preview (multi-line monospace block) including: rewritten prompt (if applicable), skill name, distinctive judgment, output contract digest. Dedupe by skill so the same skill never appears twice.
5. Surface the AskUserQuestion. The framework automatically adds an `Other` escape hatch.
6. On user selection: parse which skill + which phrasing was chosen. If the skill is `manual_only`, print the slash command for the user to run themselves. Otherwise dispatch via the `Skill` tool with the chosen phrasing as the argument.
7. Log a `route_picker_choice` event (via Bash: `py -3 -c "import scripts.ledger-v2 as l; l.write_event('route_picker_choice', chosen_id='<id>', original_top_id='<id>', was_rewrite=<bool>, option_count=<n>)"`) so the learning queue can detect when users systematically prefer non-top routes.

## Validation

The picker is a UX layer, not a code-modifying skill — validation is behavioral. Verify the user saw an AskUserQuestion with N options, picked one, and the chosen skill was actually invoked. If the chosen skill was manual_only, verify the slash command was surfaced to the user.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Original Intent
    type: section
    required: true
    evidence_rule: "verbatim user prompt"
  - field: Picker Trigger
    type: section
    required: true
    evidence_rule: "hook directive | manual invocation"
  - field: Options Presented
    type: section
    required: true
    evidence_rule: "option list with skill IDs + phrasings"
  - field: User Choice
    type: section
    required: true
    evidence_rule: "option ID + skill name + phrasing chosen"
  - field: Dispatch Action
    type: section
    required: true
    evidence_rule: "Skill tool call OR manual slash command surfaced"
  - field: Telemetry Event Written
    type: section
    required: true
    evidence_rule: "route_picker_choice event name + key fields"
```

Original Intent | Picker Trigger (hook directive | manual) | Options Presented (with previews) | User Choice (option ID + skill + phrasing) | Dispatch Action (Skill tool invocation | manual slash command surfaced) | Telemetry Event Written

## Subagent delegation

None. This is an orchestrator skill — it runs inline in the main thread because the picker is interactive (calls AskUserQuestion). The chosen downstream skill handles its own dispatch per its own dispatch policy.

## V4 aliases

This skill answers to V4 names: `pick`, `route-interactive`. The router resolves them to `choose` and notes the alias in its response.
