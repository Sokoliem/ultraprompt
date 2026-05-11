---
description: Cross-worktree dashboard. Shows every worktree's state in one screen with urgency triage.
---

Show the cross-worktree status dashboard for the current repository.

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/status-renderer.py`

For all watched repositories: pass `--all-repos`.

After displaying, recommend the highest-priority next action based on urgency:
- Worktrees in CRITICAL (in-progress merge/rebase/cherry-pick): help the user complete or abort
- Worktrees in NEEDS TRIAGE (high dirty count, many unpushed): suggest `/ultraprompt:wip-save` then `/ultraprompt:cleanup`
- Worktrees in IN FLIGHT (active session): note that another session is running; don't interfere
