---
name: "mcp-design"
description: "When user says 'design an MCP server / MCP tool design / MCP architecture / how should I expose this as MCP / MCP capability design' — dispatches reviewer/architect with MCP focus. DEFAULT for MCP design tasks."
when_to_use: "Manual-only. Invoke for MCP server design, audit, or tool-boundary review. Combines V4's mcp-integration-design and mcp-server-audit."
argument-hint: "[server|tool|surface]"
tier: "ecosystem"
aliases: ["mcp-integration-design", "mcp-server-audit"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# MCP Design

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus: `mcp`) for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `cognitive-governance-panel`, `contract-drift-panel`. Preferred: `cognitive-governance-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

MCP tools are model-callable functions with structured I/O. The interface is the contract: input schema, output shape, error mode. Tools should be read-only by default; write/destructive tools require explicit naming and ideally a confirmation gate at the consumer. Server should be dependency-free if possible (no pip install at plugin load) and should self-test via --self-test flag.

## First signals to inspect

- MCP protocol version (2025-06-18 at time of writing)
- Tool inventory: what's exposed
- Per-tool: input schema, output shape, side effects (read-only? state-modifying? external network call?)
- Error handling: tool errors vs server errors vs protocol errors
- Server lifecycle: stdio? Self-test mode? Plugin root resolution
- Dependencies: dependency-free Python is ideal; pip-installed deps require care
- Performance: how fast does each tool return? Resource limits?

## Failure modes specific to this lane

- Tool with side effect not named like a side effect (`get_status` that resets state)
- Schema that says required field but server doesn't validate
- Server crashes on invalid input instead of returning structured error
- Long-running tool with no timeout
- Tool that pulls in heavy deps (slow plugin load)
- No self-test mode (can't smoke-test without Claude Code)
- Missing protocol-level methods (initialize, tools/list, ping)

## Workflow

1. Identify the integration goal: what should the model be able to do?
2. Design the tool surface: minimal, read-only by default, named clearly.
3. Define input schema (JSON Schema) and output shape per tool.
4. Implement the server: protocol methods, error handling, self-test mode.
5. Add tool-level tests (input → expected output).
6. Smoke-test JSON-RPC end-to-end without Claude Code.
7. Wire into plugin via .mcp.json.

## Validation

Run --self-test (returns tools/list JSON). Run JSON-RPC smoke test (initialize + tools/list + tools/call for each tool). Test error cases (missing required fields, invalid types).

## Output contract

Server Purpose | Tool Inventory (per tool: side effect class, schema, output) | Self-Test Result | JSON-RPC Smoke Test Result | Plugin Integration | Recommendations

## Subagent delegation

Dispatch `auditor` with focus=infra for server resource handling. Dispatch `auditor` with focus=ai-safety for tool-boundary review when the server enables agent autonomy.

## V4 aliases

This skill answers to V4 names: `mcp-integration-design`, `mcp-server-audit`. The router resolves them to `mcp-design` and notes the alias in its response.
