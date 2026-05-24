---
description: Triage assistant for dirty trees. Groups uncommitted changes by path, size, age, and file type. Suggests actions per group.
disable-model-invocation: true
---

Triage the current worktree's dirty state.

Steps:
1. List all dirty + untracked files: `git status --porcelain=v1 -uall`
2. Group by:
   - Top-level directory (e.g., src/, tests/, docs/)
   - File type (.py, .ts, .md, etc.)
   - Change magnitude (LOC delta via `git diff --numstat` for tracked files)
   - Whether the file is gitignored content that leaked through
3. For each group, suggest one of:
   - "Looks like a formatter sweep — `git checkout -- .` to revert if not intentional"
   - "Feature work — review with `/ultraprompt:review` then commit as feature branch"
   - "Build artifacts that should be gitignored — add to .gitignore, then `git rm --cached`"
   - "Mixed scattered edits — `/ultraprompt:wip-save` first, then triage one-by-one"
4. Recommend ONE concrete next command per group.

Always offer `/ultraprompt:wip-save` first if the user is uncertain — that's reversible.
