---
name: "ai-agent-safety-review"
description: "**DEFAULT for AI agent safety reviews: dispatches security-auditor + risk-and-controls-reviewer with AI/agent safety focus: runs the ai-agent-safety-review discipline.**"
when_to_use: "Manual-only. Invoke for AI/LLM safety review: tool-calling boundaries, prompt injection vectors, retrieval trust, memory/context handling, autonomy controls, or prompt hardening for a specific prompt or skill body."
argument-hint: "[system|tool|prompt|focus]"
tier: "specialist"
aliases: ["ai-agent-safety-review", "prompt-hardening"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# AI Agent Safety Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `ai-safety`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

LLM systems have a unique attack surface: prompts and retrieved content are mixed with instructions, and the model treats both as authoritative. Trust boundaries must be explicit (this is data, that is instruction). Tool-calling is privilege escalation: each tool a model can call is an action it can take. Autonomy controls (human-in-loop, confirmation, audit) are part of the design, not afterthoughts.

## First signals to inspect

- System prompt content: are instructions clearly separated from user data?
- Retrieval pipeline: is retrieved content marked as untrusted? Is it shown verbatim to the model?
- Tool inventory: what can the model call? With what side effects?
- Memory/context: what persists across turns or sessions? Who can poison it?
- Autonomy: where does the model act vs ask?
- Output channels: where does model output go? (UI, logs, downstream systems, other models)
- Prompt injection vectors: any path where attacker-controlled text reaches the model

## Failure modes specific to this lane

- Concatenating user input directly into the system prompt
- Showing retrieved web content to the model without trust boundary marking (classic prompt injection vector)
- Tool that takes a free-text argument and executes it (shell, eval, SQL)
- Memory shared across users (one user can poison another's session)
- Auto-approval of tool calls that should require human confirmation
- Logging the full prompt + completion (often contains secrets, PII)
- Retrieved context that the model trusts as authoritative when it shouldn't

## Workflow

1. Inventory: prompts, tools, retrieval sources, memory, output channels.
2. Map trust boundaries. Confirm separation of instruction vs data.
3. Audit each tool: what does it do, what's the side-effect blast radius, what's the confirmation gate.
4. Audit retrieval: is content marked, sandboxed, or sanitized before reaching the model?
5. Audit memory/context for cross-user contamination.
6. Audit autonomy controls: where can the model act, where must it ask?
7. Audit output channels for log/audit safety.
8. Apply hardening: prompt restructuring, tool argument validation, retrieval marking, confirmation gates.

## Validation

Run prompt-injection eval cases (test corpus of known injection strings). Test tool argument validation with adversarial inputs. Test memory isolation across simulated users. For prompts: run before/after eval suite if available.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Scope
    type: section
    required: true
    evidence_rule: "none"
  - field: Trust Boundary Map
    type: section
    required: true
    evidence_rule: "none"
  - field: Tool Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Retrieval Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Memory/Context Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Autonomy Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Hardenings Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Remaining Risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
```

Scope | Trust Boundary Map | Tool Audit (per tool: side effect, confirmation gate, hardening) | Retrieval Audit | Memory/Context Audit | Autonomy Audit | Hardenings Applied | Remaining Risks

## Subagent delegation

Dispatch `auditor` with focus=ai-safety. See `_shared/playbooks/prompt-injection-patterns.md` and `_shared/playbooks/prompt-hardening-checklist.md`.

## V4 aliases

This skill answers to V4 names: `ai-agent-safety-review`, `prompt-hardening`. The router resolves them to `ai-agent-safety-review` and notes the alias in its response.
