---
name: "plugin-review"
description: "**DEFAULT for plugin review tasks: dispatches reviewer/architect with Claude/Codex plugin focus (manifest, skills, agents, MCP, hooks): runs the plugin-review discipline.**"
when_to_use: "Manual-only. Invoke for ecosystem-level review of a Claude Code plugin package. For authoring a new skill or agent, use ecosystem skills `skill-author` or `agent-author`."
argument-hint: "[plugin path|focus]"
tier: "ecosystem"
aliases: ["claude-code-plugin-review"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Plugin Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

A Claude Code plugin is a structured package: skills (with frontmatter and bodies), agents (with tool permissions), hooks (deterministic), commands, MCP servers, output styles, marketplace metadata. Each surface has its own review criteria. Hooks are the riskiest because they intercept tool calls; MCP servers run as subprocesses; skills are passive but cumulative.

## First signals to inspect

- Plugin manifest: `.claude-plugin/plugin.json` — schema, version, declared surfaces
- Skills: frontmatter validity, body shape, when_to_use clarity, tier
- Agents: tool permissions, body clarity, intended use
- Hooks: matchers, scripts, fail-open behavior, env-var disable
- Commands: scope, allowed-tools, disable-model-invocation usage
- MCP server: tool surface, side effects, error handling
- Output styles: what they actually change
- Marketplace metadata: keywords, description, source

## Failure modes specific to this lane

- Skills that auto-activate too broadly (description matches everything)
- Agents with unrestricted tool access when read-only would suffice
- Hooks that don't fail-open on parse error (could brick the session)
- MCP server that crashes the plugin if it errors
- Marketplace metadata that misrepresents what the plugin does
- Skill bodies with inlined boilerplate (V4 mistake) instead of single-discipline reference
- Plugin manifest fields that aren't valid Claude Code schema

## Workflow

1. Validate plugin manifest against Claude Code schema.
2. Audit skills: frontmatter, body shape, tier, when_to_use clarity, no inlined boilerplate.
3. Audit agents: tool permissions least-privilege, body clarity.
4. Audit hooks: matcher precision, fail-open behavior, env-var disable, evidence logging.
5. Audit commands: appropriate scope, allowed-tools restrictions where possible.
6. Audit MCP server: read-only by default, error handling, resource limits.
7. Audit marketplace metadata: accuracy.
8. Apply concrete fixes for clear violations; flag policy questions.

## Validation

Run the plugin's bundled validator and doctor commands if present. Smoke test: load the plugin in a test repo, exercise each surface, confirm hooks block expected destructive commands, confirm MCP server self-test passes.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Plugin Manifest Status
    type: section
    required: true
    evidence_rule: "none"
  - field: Skills Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Agents Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Hooks Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Commands Audit
    type: section
    required: true
    evidence_rule: "command + exit code + excerpt"
  - field: MCP Server Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Marketplace Metadata Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Fixes Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommendations
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
```

Plugin Manifest Status | Skills Audit (per skill) | Agents Audit | Hooks Audit | Commands Audit | MCP Server Audit | Marketplace Metadata Audit | Fixes Applied | Recommendations

## Subagent delegation

Dispatch `auditor` with focus=plugin for second perspective.

## V4 aliases

This skill answers to V4 names: `claude-code-plugin-review`. The router resolves them to `plugin-review` and notes the alias in its response.
