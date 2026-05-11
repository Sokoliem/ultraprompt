---
description: Plugin usage analytics from the always-on ledger. Skill heat map, MCP tool calls, WIP save count, claim-check trips.
---

Show plugin usage analytics from the ledger.

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py summary --days 7`

For longer windows: `--days 30` or `--days 90`.

Output includes:
- Total events by type
- Top skills invoked
- Top MCP tools called
- Top repos touched
- WIP saves made
- Claim-check trips
- Sessions started

Use this to understand what's actually getting used so V8 and beyond can be evidence-driven.
