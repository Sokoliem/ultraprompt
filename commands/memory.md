---
description: Query and govern Ultraprompt V8 typed memory: candidates, promotion, lifecycle, export, forget, and stats.
argument-hint: "[query|write-candidate|promote|forget|stats|export] [filters]"
---

# Ultraprompt Memory

Use typed, local-first V8 memory with evidence, scope, privacy, and status controls.

## Usage

- `/ultraprompt:memory stats`
- `/ultraprompt:memory query --text "repo fact" --scope repo`
- `/ultraprompt:memory write-candidate --kind repo_fact --scope repo --text "..."`
- `/ultraprompt:memory promote <memory_id> --evidence file:path`
- `/ultraprompt:memory forget <memory_id>`

## Dispatch

Prefer MCP tools: `memory_query`, `memory_write_candidate`, `memory_promote`, `memory_forget`, and `memory_stats`.
Use `scripts/memory-store.py` for CLI-equivalent local diagnostics.
