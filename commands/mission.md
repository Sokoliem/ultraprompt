---
description: V8. Mission Control — unified state snapshot. Repo + worktree + sessions + evidence + WIP snapshots + gap ledger + available panels in one view.
argument-hint: [--write] [--path <worktree>]
---

# Mission Control

Show unified Ultraprompt state for the current repo and active sessions.

## Execution

1. Call the `mission_state` MCP tool with current path (or `--path` if provided).
2. If `--write` argument supplied, also persist snapshot to `~/.ultraprompt/state/mission-state.json`.
3. Format output as readable summary:

```
Mission Control — <repo>@<worktree>

Runtime
  Plugin: <version>
  Runtime: <claude|codex>

Repo
  Branch: <branch>  HEAD: <sha>  Stash: <count>  Unpushed: <count>

Worktree
  Dirty: <count>  Untracked: <count>  Staged: <count>

Sessions
  Active in this worktree (last 15 min): <count>
  Concurrent worktrees: <list>

Evidence (24h)
  Total events: <count>
  Top types: <list>

Recovery
  WIP snapshots: <count>  Latest: <branch name>

Gaps
  Total: <total_gap_ids>  Open: <open>  Critical: <critical>  High: <high>

Panels available
  - repo-completeness-panel (8 agents, ~25 min)
  - feature-gap-panel (5 agents, ~12 min)
  - contract-drift-panel (4 agents, ~10 min)
  - release-gate-panel (6 agents, ~18 min)
  - prd-panel (5 agents, ~22 min)
  - ai-feature-panel (6 agents, ~28 min)
  - idea-panel (5 agents, ~20 min)
  - mvp-panel (4 agents, ~15 min)
  - cognitive-governance-panel (6 agents, ~18 min)
  - security-privacy-panel (6 agents, ~22 min)
  - migration-readiness-panel (6 agents, ~20 min)
  - incident-response-panel (6 agents, ~16 min, confirmation required)

[ Run /ultraprompt:panel-run <panel-name> for coordinated audit ]
```

## When to use

- Starting a new session and want to know what's already in flight.
- Suspecting concurrent sessions modifying the same worktree.
- After a long break — what was I doing, what's pending validation, what gaps exist.
- Before deciding whether to dispatch a panel — see what state already exists.

## Anti-patterns

- Do not run inside loops or hooks — Mission Control reads multiple stores; not free.
- Do not paste full snapshot to chat — summarize. Persist via `--write` if user wants the JSON.
