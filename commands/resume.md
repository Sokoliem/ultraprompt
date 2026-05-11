---
description: Resume from previous session. Reads last session transcript + WIP branches + current state and produces "where was I" summary.
---

Restore session context for the current worktree.

Steps:
1. Find last Claude Code session JSONL: scan `~/.claude/projects/<encoded-current-path>/` for newest `*.jsonl` by mtime.
2. Read the last 50 events from that JSONL — capture last user prompt, last assistant action, validation runs.
3. List WIP branches for this worktree: `git branch --list 'wip/<repo>/<worktree>/*' --sort=-committerdate | head -10`.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/worktree-state.py worktree $(pwd)` for current dirty/unpushed state.
5. Synthesize: "Last session ended X ago. Last action: ... Current dirty state: ... Recommended next: ..."

If no prior session JSONL exists, say so cleanly and proceed with current state only.
