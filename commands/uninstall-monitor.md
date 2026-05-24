---
description: Uninstall the launchd worktree monitor.
disable-model-invocation: true
---

Uninstall the launchd-driven worktree monitor.

Run: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/install-launchd.sh uninstall`

Removes both agents (scan + digest), unloads from launchd, deletes plists. Ledger and config remain intact.
