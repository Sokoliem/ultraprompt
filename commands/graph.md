---
description: Show V8 capability graph health, node counts, edge counts, and stale/missing references.
argument-hint: "[--json|--check]"
---

# Ultraprompt Capability Graph

Inspect generated graph coverage across skills, agents, commands, panels, MCP tools, artifacts, validators, hooks, ledgers, and dream jobs.

## Usage

- `/ultraprompt:graph`
- `/ultraprompt:graph --check`

## Dispatch

Invoke `capability_graph`. Use `scripts/build-capability-graph.py --check` for release-gate freshness.
