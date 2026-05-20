#!/usr/bin/env bash
set -euo pipefail
[[ "${ULTRAPROMPT_DISABLE_HOOKS:-0}" == "1" ]] && exit 0

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Ultraprompt V8.3.0 active - cognitive control plane release. Catalog: 54 skills, 31 agents, 43 MCP tools, 31 commands, 13 panels, 27 artifact schemas.\n\n**V8.3 adds:**\n- Source-derived routing policy and Invocation Director trigger plans.\n- Panel-aware pathfinding with confidence gaps, route replay, and live adoption gates.\n- Cognitive memory with candidate, promotion, stale, and forget flows.\n- Dream jobs for read-only background synthesis and release hygiene.\n- Learning queue for reviewable routing and catalog improvements.\n- Live dashboard telemetry from Claude Code and Codex ledgers plus V8 cognitive streams.\n\n**FIRST RULE:** when uncertain how to handle a request, call `route_trigger_plan` or `dispatch_advise` MCP tool. They return a dry-run route or dispatch-vs-inline guidance with a concrete agent, skill, or panel.\n\n**Dispatch defaults:**\n| Pattern | Skill / Agent |\n|---|---|\n| Whole-repo audit | `/ultraprompt:repo-review` -> `ultraprompt:repo-cartographer` |\n| Repo discovery | `/ultraprompt:repo-map` -> `ultraprompt:scout` |\n| Diff/PR review | `/ultraprompt:review` -> `ultraprompt:reviewer` |\n| Failing test/runtime bug | `/ultraprompt:debug` -> `ultraprompt:debugger` |\n| Auth/secrets/injection | `/ultraprompt:security-audit` -> `ultraprompt:security-auditor` |\n| Architecture | `/ultraprompt:architect` -> `ultraprompt:reviewer` with architecture focus |\n| Test strategy | `/ultraprompt:test-harden` -> `ultraprompt:test-strategist` |\n| Release/docs | `/ultraprompt:release` or `/ultraprompt:docs-sync` -> `ultraprompt:writer` |\n| Red-team/critique | `/ultraprompt:panel-run adversarial` -> `ultraprompt:adversarial` |\n\n**Inline-only skills:** `build`, `refactor`, `migrate`, `llm-eval-design`, `tui-design-innovate`, `contract-test-generate`.\n\n**Safety:** write evidence for validation claims, use `/ultraprompt:wip-save` before risky work, and apply `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md`."
  }
}
JSON
