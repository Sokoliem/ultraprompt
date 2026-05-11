---
description: Explain the recommended Ultraprompt skill, agent, command, panel, or staged workflow for a user goal.
argument-hint: "<intent> [--repo path] [--budget low|standard|deep]"
---

# Ultraprompt Pathfinder

Return an explainable workflow path with confidence, alternatives, memory influences, expected artifacts, graph hash, risk, and confirmation metadata.

## Usage

- `/ultraprompt:pathfind review this plugin before release`
- `/ultraprompt:pathfind "plan the postgres migration" --budget deep`

## Dispatch

Invoke `pathfind_workflow` with `dry_run=true` by default. Do not execute the recommended path unless the user separately asks to run it.
