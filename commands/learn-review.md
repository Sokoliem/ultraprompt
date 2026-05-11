---
description: Review, approve, apply, reject, or revert governed V8 learning candidates.
argument-hint: "[list|approve|apply|reject|revert|stats] [candidate_id]"
---

# Ultraprompt Learn Review

Govern V8 learning. Learning proposals never silently mutate prompts, source specs, or user repositories. Route policy overlays are validated and reversible.

## Usage

- `/ultraprompt:learn-review list`
- `/ultraprompt:learn-review approve <candidate_id>`
- `/ultraprompt:learn-review apply <candidate_id>`
- `/ultraprompt:learn-review revert <candidate_id>`

## Dispatch

Use MCP tools `learning_candidates` and `learning_apply`; use `scripts/learning-queue.py` when a CLI trace is needed.
