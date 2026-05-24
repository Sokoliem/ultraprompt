---
description: Create a new git worktree with plugin-aware setup. Records intent to ledger.
disable-model-invocation: true
---

Create a new git worktree with the given name and optional purpose.

Steps:
1. From current repo: `git worktree add ../<repo>-<name> -b <name>` (or use existing branch with `--checkout`)
2. Record to ledger: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py write worktree_created --field repo=<name> --field worktree=<path> --field branch=<branch> --field intent="<purpose>"`
3. Tell user to `cd` into the new worktree.

If user has standing `.claude-worktrees/` convention (detect via parent dir), honor that placement.

Ask the user for: name, branch (new or existing), and a one-line purpose.
