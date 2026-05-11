---
name: "prd-ai-feature"
description: "When user says 'PRD for an AI feature / LLM-based feature spec / agent feature PRD / ML product requirements / generative AI feature / RAG feature spec / AI-powered X' — produces a PRD with AI-specific sections (model selection rationale, eval methodology, groundedness/hallucination guardrails, safety filters, human-in-the-loop fallback, cost model, latency targets, prompt versioning strategy, data privacy posture). DEFAULT for any feature whose core capability comes from an LLM, ML model, or AI/agent system. Different from prd-technical (general engineering): prd-ai-feature specifically handles AI-product risks (eval, safety, cost, hallucination, drift)."
when_to_use: "When the feature's core capability comes from an LLM, ML model, or AI agent. The risks (eval, hallucination, cost, safety) are categorically different from non-AI features."
argument-hint: "<AI feature name or capability>"
tier: "core"
aliases: ["ai-prd", "llm-feature-prd", "agent-prd"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# AI Feature PRD

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:principal-pm`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

PRD-ai-feature is for AI/LLM/agent features specifically; prd-technical is general engineering; prd-standard is general product. The AI-specific sections (eval, groundedness, cost, safety) require dedicated handling.

## First signals to inspect

- Feature relies on LLM, ML model, or agent.
- User mentions 'AI', 'GPT', 'Claude', 'agent', 'RAG', 'embedding', 'fine-tune', or model names.
- Output quality is probabilistic, not deterministic.

## Failure modes specific to this lane

- Treating AI feature like deterministic software — missing eval/safety/hallucination handling.
- No cost model (AI features have non-trivial unit costs).
- No human-in-the-loop fallback for low-confidence outputs.
- Missing prompt/model versioning strategy (untracked drift).

## Workflow

1. Dispatch principal-pm for problem + users + goals + non-goals.
2. Dispatch technical-product-architect for system design with AI-specific sections.
3. Dispatch evaluator for eval methodology (offline eval, human eval, online metrics).
4. Dispatch risk-and-controls-reviewer for safety/bias/privacy/data-handling.
5. Combine into single PRD-ai-feature artifact with explicit AI sections.
6. End with open questions ordered by blocking-priority.

## Validation

Every AI feature PRD must explicitly address: model selection rationale, eval methodology (both offline and online), groundedness/hallucination guardrails, safety filters, human-in-the-loop fallback path, cost model (per-call + scaled), latency budget, prompt versioning, and data privacy posture (training data, retention, opt-out).

## Output contract

Problem statement + evidence | Users + jobs-to-be-done | Goals + non-goals | Must/should/won't-have requirements | Scope (in/out) | Technical design with AI sections | AI: model selection rationale + alternative models considered | AI: eval methodology (offline benchmarks, online metrics, human eval if applicable) | AI: groundedness + hallucination guardrails | AI: safety filters + content policy | AI: human-in-the-loop fallback path + low-confidence handling | AI: cost model (per-call + scaled to expected QPS) | AI: latency targets + budget | AI: prompt versioning + model versioning strategy | AI: data privacy posture (training data, retention, opt-out, residency) | AI: drift monitoring + retraining trigger criteria | Risks + acceptance criteria + rollout plan + validation plan + open questions

## Subagent delegation

Default: chain principal-pm → technical-product-architect → evaluator → risk-and-controls-reviewer. This is intentionally a 4-agent chain because AI features have multiple risk surfaces.

## V4 aliases

This skill answers to V4 names: `ai-prd`, `llm-feature-prd`, `agent-prd`. The router resolves them to `prd-ai-feature` and notes the alias in its response.
