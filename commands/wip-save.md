---
description: Safely snapshot dirty state to a wip/<repo>/<worktree>/<timestamp> branch without affecting current work. Always recoverable.
disable-model-invocation: true
---

Save the current worktree's dirty state to a recoverable WIP branch.

Run: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/wip-save.py --trigger manual`

Pass through any of: `--push` (push to backup remote), `--no-untracked` (exclude untracked files), `--message "<text>"`.

Refuses to wip-save if:
- An in-progress operation is active (merge/rebase/cherry-pick/bisect/revert)
- Working tree is clean (nothing to save)

After save, the WIP branch is browsable: `git log wip/<repo>/<worktree>/<timestamp>` and recoverable via `git checkout` or cherry-pick.
