---
name: "cost-audit"
description: "**DEFAULT for cost analysis spanning LLM tokens, cloud spend, and database query cost — produces a ranked findings list with monthly $-cost estimate, severity, and remediation suggestion per item.** Different from /auditor (general single-concern auditor — this skill is specifically cost-focused with $-amount evidence), /performance-pass (latency, not $-spend), /supply-chain-hardening (dependency security, not cost). Triggers: 'cost audit, llm cost, cloud cost, expensive query, n+1, runaway tokens, save money, hot path spending'."
when_to_use: "Use when the team wants to understand where money is leaking — LLM tokens in hot paths, cloud resources that aren't trimmed, N+1 query patterns, unbatched API calls. Dispatches data-analyst agent."
argument-hint: "[scope|focus: llm|cloud|db|all]"
tier: "specialist"
aliases: ["cost-analysis", "spend-audit", "llm-cost-audit"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Cost Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Cost analysis without $-amount evidence is hand-waving. Every finding must include a monthly-cost estimate (even if rough) so engineering can prioritize against effort. Three sub-domains differ: LLM (token waste), cloud (untrimmed resources), DB (query patterns). Each needs its own evidence vocabulary.

## First signals to inspect

- Cloud billing line items (top 5 services by spend)
- LLM call sites: model selection, max_tokens, cache-hit ratio
- Database slow-query log; N+1 patterns; missing indexes
- Hot-path call counts (which functions invoke LLM/cloud/db)
- Cost reports from the last 30/60/90 days

## Failure modes specific to this lane

- Generic 'reduce cost' advice with no monthly-$ estimate
- Optimizing the wrong axis (latency-tuning when the cost driver is volume)
- Recommending model downgrades without quality measurement
- Missing the N+1 pattern because individual queries look cheap
- Audit limited to LLM when DB is the real cost driver

## Workflow

1. Identify scope (LLM / cloud / db / all).
2. For LLM: enumerate call sites; estimate monthly tokens × per-token cost.
3. For cloud: top 5 billing lines; identify untrimmed / overprovisioned.
4. For DB: slow-query log; N+1 detection; missing-index detection.
5. Rank findings by monthly-$ impact × effort-to-fix.
6. Surface systemic patterns (e.g., 'all LLM calls use max_tokens=4096 even when 512 would do').

## Validation

Every finding has a $-amount estimate and remediation. No finding without dollars.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Scope + Focus
    type: section
    required: true
    evidence_rule: "none"
  - field: Findings
    type: section
    required: true
    evidence_rule: "none"
  - field: Systemic Patterns
    type: section
    required: true
    evidence_rule: "none"
  - field: Recommended Sequencing
    type: section
    required: true
    evidence_rule: "none"
  - field: Expected Savings
    type: section
    required: true
    evidence_rule: "none"
```

Scope + Focus | Findings (file:line + monthly-$ + severity) | Systemic Patterns | Recommended Sequencing | Expected Savings

## Subagent delegation

Dispatch data-analyst agent for cost-data interpretation. Pair with /performance-pass if latency improvements would also help cost.

## V4 aliases

This skill answers to V4 names: `cost-analysis`, `spend-audit`, `llm-cost-audit`. The router resolves them to `cost-audit` and notes the alias in its response.
