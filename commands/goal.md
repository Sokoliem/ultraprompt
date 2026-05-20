---
description: Set, inspect, or clear a transcript-backed goal contract for substantial work with a verifiable completion condition.
argument-hint: "[condition|status|clear] [--max-turns N|--until command]"
---

# Ultraprompt Goal

Use a measurable completion condition as the stop rule for the current session. This is the Codex-compatible bridge for Claude Code's built-in `/goal` behavior.

## Usage

- `/ultraprompt:goal all tests in test/auth pass and lint exits 0`
- `/ultraprompt:goal status`
- `/ultraprompt:goal clear`

Codex does not route plugin command markdown through its native `/` slash parser. In Codex, use `$ultraprompt:goal ...`, plain `ultraprompt:goal ...`, or natural language such as "set a goal to keep working until tests pass."

## Contract

One active goal condition should be visible in the transcript. The assistant must surface proof after meaningful work: command exit codes, screenshot evidence, file counts, checklist status, or artifact validation. If the condition cannot be proven, report `blocked` rather than `met`.

Claude Code's built-in `/goal` uses a session-scoped Stop-hook evaluator. This plugin command does not claim that Codex has that loop; it gives Codex a main-thread goal discipline that is inspectable and compatible with `$ultraprompt:goal`.

Goal output must include the condition, acceptance criteria, proof method, bounds, status, evidence references, and the runtime distinction: Codex receives a transcript-backed bridge, while Claude Code may also have native built-in `/goal` evaluator behavior outside the plugin.
