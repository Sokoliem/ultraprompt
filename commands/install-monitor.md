---
description: Install the launchd-driven worktree monitor. Scans every 30 min, daily digest at 9 AM, macOS notifications on urgent state.
---

Install the launchd worktree monitor for between-session safety.

Run: `bash ${CLAUDE_PLUGIN_ROOT}/scripts/install-launchd.sh install`

After install:
- Two launchd agents are loaded: scan (every 30 min) and digest (daily 9 AM)
- macOS notifications fire on urgent worktree state (respects quiet hours config)
- Auto-WIP-save runs in background if `auto_wip_save.enabled = true`
- Logs at `~/.claude/ultraprompt-data/launchd-monitor.{out,err}`

Verify: `launchctl list | grep ultraprompt`

To uninstall later: `/ultraprompt:uninstall-monitor`

The monitor needs `~/.claude/ultraprompt.toml` with `[watched_repos] paths = ["~/development"]` (or your dev base) — without that, it has nothing to scan.
