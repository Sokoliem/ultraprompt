---
name: "prd-ai-feature"
description: "**DEFAULT for PRD FOR AN AI/LLM/AGENT FEATURE — model selection rationale, eval plan, safety boundaries, cost envelope, failure-mode map: PRD covering AI-specific sections (model selection, eval design, safety boundaries, cost envelope, failure-mode map) on top of the standard PRD shape.** Different from /prd-standard (non-AI features), /prd-technical (deep tech-design PRD, not AI-specific), /llm-eval-design (eval design only). Triggers: 'PRD for an AI feature, AI-feature spec, agent feature PRD, LLM feature spec, model-backed feature'."
when_to_use: "When the feature's core capability comes from an LLM, ML model, or AI agent. The risks (eval, hallucination, cost, safety) are categorically different from non-AI features."
argument-hint: "<AI feature name or capability>"
tier: "core"
aliases: ["ai-prd", "llm-feature-prd", "agent-prd"]
output_style: "evidence-led"
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

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Problem statement + evidence
    type: section
    required: true
    evidence_rule: "file:line citation, command output, or doc reference required"
  - field: Users + jobs-to-be-done
    type: section
    required: true
    evidence_rule: "none"
  - field: Goals + non-goals
    type: section
    required: true
    evidence_rule: "none"
  - field: Must/should/won't-have requirements
    type: section
    required: true
    evidence_rule: "none"
  - field: Scope
    type: section
    required: true
    evidence_rule: "none"
  - field: Technical design with AI sections
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: model selection rationale + alternative models considered
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: eval methodology
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: groundedness + hallucination guardrails
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: safety filters + content policy
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: human-in-the-loop fallback path + low-confidence handling
    type: section
    required: true
    evidence_rule: "label: High|Medium|Low"
  - field: AI: cost model
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: latency targets + budget
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: prompt versioning + model versioning strategy
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: data privacy posture
    type: section
    required: true
    evidence_rule: "none"
  - field: AI: drift monitoring + retraining trigger criteria
    type: section
    required: true
    evidence_rule: "none"
  - field: Risks + acceptance criteria + rollout plan + validation plan + open questions
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
```

Problem statement + evidence | Users + jobs-to-be-done | Goals + non-goals | Must/should/won't-have requirements | Scope (in/out) | Technical design with AI sections | AI: model selection rationale + alternative models considered | AI: eval methodology (offline benchmarks, online metrics, human eval if applicable) | AI: groundedness + hallucination guardrails | AI: safety filters + content policy | AI: human-in-the-loop fallback path + low-confidence handling | AI: cost model (per-call + scaled to expected QPS) | AI: latency targets + budget | AI: prompt versioning + model versioning strategy | AI: data privacy posture (training data, retention, opt-out, residency) | AI: drift monitoring + retraining trigger criteria | Risks + acceptance criteria + rollout plan + validation plan + open questions

## Subagent delegation

Default: chain principal-pm → technical-product-architect → evaluator → risk-and-controls-reviewer. This is intentionally a 4-agent chain because AI features have multiple risk surfaces.

## V4 aliases

This skill answers to V4 names: `ai-prd`, `llm-feature-prd`, `agent-prd`. The router resolves them to `prd-ai-feature` and notes the alias in its response.
