---
description: Show hook-recorded commands, validation events, edit events, hook blocks, and subagent events from the evidence ledger.
disable-model-invocation: true
argument-hint: [--json]
---

# Evidence Report

Print the evidence ledger summary.

Run:

- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-ledger.py" path` to show the ledger location
- `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-ledger.py" report $ARGUMENTS` for the summary (use `--json` if the user passed it)

If the ledger is empty, say so plainly. If it does not exist yet, that's expected on a fresh session — explain that hooks populate it as tools are used.

Surface the most useful items first:

- Validation commands run in this session (with results)
- Edit events (with file paths, no content)
- Hook blocks (destructive command, protected file, claim gate) with reasons
- Subagent dispatch events (with target agent and task summary)

Keep the report compact. Do not print the full JSONL.
