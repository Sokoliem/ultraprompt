---
description: Restore the working tree to the most recent wip-save snapshot or named checkpoint. Companion to /ultraprompt:wip-save and /ultraprompt:checkpoint.
argument-hint: "[<checkpoint-id>|--latest|--list]"
disable-model-invocation: true
allowed-tools: "Read, Bash"
---

# Worktree Rollback (V8.9)

Restore the working tree to a previously saved state. Uses ledger v2 events
(`wip_save`, `checkpoint`) as the source of truth; never rewrites history.

## Usage

```
/ultraprompt:rollback --latest       # restore to most recent wip-save or checkpoint
/ultraprompt:rollback --list         # show last 10 rollback-eligible snapshots
/ultraprompt:rollback <event-id>     # restore to a specific snapshot
```

## Workflow

1. Parse `$ARGUMENTS`. If empty, print usage + last 5 snapshots and exit.
2. Query the V8 ledger for recent `wip_save` and `checkpoint` events, scoped to the current worktree.
3. Select the target snapshot:
   - `--latest`: pick the most recent event whose worktree matches `cwd`.
   - `--list`: print the 10 most recent and exit (no mutation).
   - explicit id: look up by event_id; on miss, exit with error and nearest 3 matches.
4. Show a diff summary (`git diff HEAD <target-sha>`), ask the user to confirm via `AskUserQuestion`, then apply:
   - For `wip_save` events: `git stash apply` the stash entry referenced by the event, or `git checkout` the wip branch (depending on `event.implementation`).
   - For `checkpoint` events: `git checkout <sha>` for a detached snapshot inspection (does not move main branch).
5. Write a `rollback-invoked` event with `{target_event_type, restored_to, dry_run}`.

## Safety

- `disable-model-invocation: true` — must be invoked by the user.
- Asks for explicit confirmation before mutating the working tree.
- Never rewrites history (no `git reset --hard`, no `git push --force`).
- If the working tree is dirty before rollback, refuses unless the user passes `--force` (in which case it first calls `/ultraprompt:wip-save` to snapshot current state).

## Distinct from peers

- **`/ultraprompt:wip-save`** — creates the snapshot. This command restores from it.
- **`/ultraprompt:checkpoint`** — creates a named checkpoint event. This command restores to one.
- **`git reset --hard`** — destructive history rewrite. This command is non-destructive; it applies a stash or checks out a commit.
