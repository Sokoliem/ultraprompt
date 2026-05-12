#!/usr/bin/env bash
set -euo pipefail

if [[ "${ULTRAPROMPT_DISABLE_HOOKS:-0}" == "1" ]]; then
  exit 0
fi

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "SubagentStart",
    "additionalContext": "Return concise, evidence-tagged findings. Prefer Observed > Inferred > Assumed claims. Stay read-only unless the parent task explicitly grants edits. Do not claim validation you did not run. When uncertain, name the highest-leverage next inspection target instead of padding the answer. Apply discipline per ${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md."
  }
}
JSON
