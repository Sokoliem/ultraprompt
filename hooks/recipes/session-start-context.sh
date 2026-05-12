#!/usr/bin/env bash
set -euo pipefail
[[ "${ULTRAPROMPT_DISABLE_HOOKS:-0}" == "1" ]] && exit 0

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "Ultraprompt V8.0.0 active - cognitive control plane release. Catalog: 48 skills, 29 agents, 42 MCP tools, 30 commands, 8 panels, 17 artifact schemas.\n\n**V8 adds:**\n- Cognitive memory with candidate, promotion, stale, and forget flows.\n- Dream jobs for read-only background synthesis and release hygiene.\n- Learning queue for reviewable routing and catalog improvements.\n- Pathfinder workflow routing backed by the capability graph.\n- Live dashboard telemetry from Claude Code and Codex ledgers plus V8 cognitive streams.\n\n**FIRST RULE:** when uncertain how to handle a request, call `dispatch_advise` MCP tool. It returns dispatch-vs-inline guidance with a concrete agent or skill.\n\n**Dispatch defaults:**\n| Pattern | Skill / Agent |\n|---|---|\n| Whole-repo audit | `/ultraprompt:repo-review` -> `ultraprompt:repo-cartographer` |\n| Repo discovery | `/ultraprompt:repo-map` -> `ultraprompt:scout` |\n| Diff/PR review | `/ultraprompt:review` -> `ultraprompt:reviewer` |\n| Failing test/runtime bug | `/ultraprompt:debug` -> `ultraprompt:debugger` |\n| Auth/secrets/injection | `/ultraprompt:security-audit` -> `ultraprompt:security-auditor` |\n| Architecture | `/ultraprompt:architect` -> `ultraprompt:reviewer` with architecture focus |\n| Test strategy | `/ultraprompt:test-harden` -> `ultraprompt:test-strategist` |\n| Release/docs | `/ultraprompt:release` or `/ultraprompt:docs-sync` -> `ultraprompt:writer` |\n| Red-team/critique | `/ultraprompt:panel-run adversarial` -> `ultraprompt:adversarial` |\n\n**Inline-only skills:** `build`, `refactor`, `migrate`, `llm-eval-design`, `tui-design-innovate`, `contract-test-generate`.\n\n**Safety:** write evidence for validation claims, use `/ultraprompt:wip-save` before risky work, and apply `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md`."
  }
}
JSON
