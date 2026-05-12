---
name: "goal"
description: "When user says '/goal / set a goal / keep working until X / completion condition / work until tests pass / do not stop until criteria are met' - provides a Codex-compatible goal contract inspired by Claude Code `/goal`. DEFAULT for substantial work with a measurable end state where Codex should keep the current turn focused on acceptance criteria and transcript-backed validation."
when_to_use: "Use when the user gives a verifiable completion condition and wants Codex to continue within the current session until that condition is met, blocked, or explicitly cleared. This is a Codex bridge for goal-oriented work; unlike Claude Code built-in `/goal`, it cannot install a session-scoped evaluator loop by itself, so it must surface proof in the transcript and stop only with met/blocked/cleared status."
argument-hint: "[condition|status|clear] [--max-turns N|--until command]"
tier: "core"
aliases: ["keep-working", "completion-goal", "goal-mode", "codex-goal"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Goal

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Inline execution policy (V8)

Prefer main-thread execution for the core workflow because goal state and completion proof must stay visible in the main conversation transcript and Codex does not provide a plugin-owned Stop-hook evaluator loop. Use subagents only for bounded discovery, critique, or test-strategy sidecars when that does not block the immediate implementation path.

## Distinctive judgment

A useful goal is a measurable completion condition, not a vague aspiration. The evaluator, whether human or model, can only judge evidence surfaced in the transcript. Make the proof explicit: command exit codes, test output, file counts, accepted acceptance criteria, or an empty queue. Bound long goals by time, turn count, or explicit stop condition so autonomy stays inspectable.

## First signals to inspect

- A completion condition phrased as an observable state: tests pass, build exits 0, checklist is complete, file budget met, issue queue empty.
- A proof method: exact command, screenshot, diff check, status output, or artifact validation result.
- Constraints: forbidden files, no unrelated changes, no destructive commands, max turns/time, runtime budget, or stop-after condition.
- Current goal status request: no arguments, status, clear, stop, off, reset, none, or cancel.
- Runtime distinction: Claude Code built-in `/goal` vs Codex `$ultraprompt:goal` skill/command bridge.
- Need for transcript evidence because no external evaluator can inspect files or run tools independently.

## Failure modes specific to this lane

- Accepting a goal like "make it good" without rewriting it into measurable acceptance criteria.
- Stopping after a plan when the user asked to keep working until proof exists.
- Claiming the goal is met without surfacing command output or explicit evidence in the transcript.
- Running indefinitely without a turn/time/budget stop condition for broad goals.
- Assuming Codex has Claude Code built-in `/goal` session hooks or status indicator.
- Clearing or replacing a goal without making the active condition visible.

## Workflow

1. Parse the argument as status, clear/cancel, or a new completion condition; aliases clear/stop/off/reset/none/cancel remove the active goal contract.
2. If setting a goal, rewrite it into acceptance criteria with proof method, constraints, and an autonomy bound when the user did not provide one.
3. Execute the immediate work path in the current turn using the relevant skills/tools while preserving the goal condition as the stop rule.
4. After each meaningful implementation or investigation step, surface evidence against the condition and decide met, not met, blocked, or cleared.
5. When the goal is met, report the exact evidence and validation. When blocked, report the blocker and the smallest next action.
6. In Claude Code, note that `/goal` is built in; in Codex, use `$ultraprompt:goal ...` or natural language because plugin slash commands are not native-routed.

## Validation

A goal is valid only when the final response includes transcript-visible proof: commands run and exit results, screenshots/artifacts inspected, file/diff checks, or explicit checklist evidence. If proof cannot be gathered, mark the goal blocked rather than met. For long goals, include the current condition, elapsed work, turns/checks performed, and latest reason.

## Output contract

Goal condition | Acceptance criteria | Proof method | Constraints/bounds | Runtime distinction (Codex bridge vs Claude Code native evaluator availability) | Current status (active/met/blocked/cleared) | Evidence surfaced | Work completed | Next action if not met

## Subagent delegation

Do not dispatch by default. Goal management is a main-thread control contract; use subagents only for bounded sidecar discovery or critique when the immediate goal path is not blocked by their result.

## V4 aliases

This skill answers to V4 names: `keep-working`, `completion-goal`, `goal-mode`, `codex-goal`. The router resolves them to `goal` and notes the alias in its response.
