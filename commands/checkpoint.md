---
description: Manually snapshot the current worktree state to the ledger. Useful before risky operations.
---

Snapshot the current worktree state to the ledger as a manual checkpoint.

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py write checkpoint --field repo=$(python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worktree-state.py repo-name) --field worktree=$(pwd) --field reason=manual`

This creates a `checkpoint` event the user can later diff against via `/ultraprompt:resume` or query via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py query --type checkpoint`.

Useful before:
- Major refactor work
- Branch switches with uncommitted state
- Long-running test suites where you want a baseline
