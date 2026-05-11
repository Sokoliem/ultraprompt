---
name: "agent-author"
description: "When user says 'author a new agent / write an agent / design an agent / new subagent / create an agent for X / agent description' — produces a new agent definition (.md with frontmatter + body) following the V8 quality bar (USE WHEN/DEFAULT/DO NOT triggers + required output contract + lane boundaries + anti-patterns). DEFAULT for agent authoring."
when_to_use: "Manual-only. Invoke for new agent authoring or refining an existing agent. Also covers agent orchestration patterns and team-style invocation design."
argument-hint: "[agent name|target]"
tier: "ecosystem"
aliases: ["agent-authoring", "agent-orchestration-plan", "agent-team-playbook"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Agent Author

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

A good agent has tight tool permissions (least-privilege), a sharp body that explains what it does and what it returns, and a clear use case. Parameterized agents (reviewer, auditor with focus arg) collapse many would-be-distinct agents into one. Agent value comes from context isolation, not from prose specialization.

## First signals to inspect

- Agent fleet in this plugin (29 agents in V8; for shape reference)
- Tool permission patterns (Read/Grep/Glob for read-only; +Bash for discovery; Write only for narrow scratch use)
- Existing parameterized agents (reviewer, auditor) — could the new agent be a focus arg instead?
- Orchestration: when is this agent dispatched? By which skills?

## Failure modes specific to this lane

- Adding a new agent when an existing parameterized one would do
- Tool permissions too broad (Write+Edit when read-only suffices)
- Body that duplicates DISCIPLINE.md content
- No clear return contract (caller doesn't know what to expect)
- Orchestration unclear: which skill spawns this agent?

## Workflow

1. Confirm the agent is needed: existing agent (parameterized or not) doesn't cover the role.
2. Draft frontmatter: name, description, max_turns, tools, disallowed_tools, color.
3. Apply least-privilege to tools.
4. Draft body: what this agent does, what it returns, behavior with discipline reference.
5. Update orchestration: which skills dispatch this agent and when.
6. Validate via plugin validator.

## Validation

Run validate-plugin.py. Smoke-test: dispatch the agent from a parent skill in a test scenario; confirm it returns the expected structured output.

## Output contract

Agent Frontmatter | Tool Permission Justification | Body Sections | Return Contract | Orchestration Update | Validator Result

## Subagent delegation

Dispatch `writer` for body prose. See `_shared/playbooks/agent-team-orchestration-patterns.md`.

## V4 aliases

This skill answers to V4 names: `agent-authoring`, `agent-orchestration-plan`, `agent-team-playbook`. The router resolves them to `agent-author` and notes the alias in its response.
