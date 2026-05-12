---
name: "llm-eval-design"
description: "When user says 'how do we evaluate this LLM feature / eval plan for AI / measure model quality / offline eval / online eval / LLM benchmarks for our use case / agent evaluation strategy' — dispatches evaluator for AI/LLM-specific evaluation design (offline + online metrics, groundedness, hallucination, drift, cost, latency). DEFAULT for LLM/agent eval design."
when_to_use: "Manual-only. Invoke for eval suite design: rubrics, golden cases, graders, thresholds. For runtime safety review of an LLM system, use specialist `ai-agent-safety-review`."
argument-hint: "[system|capability|prompt under test]"
tier: "specialist"
aliases: ["llm-eval-design"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# LLM Eval Design

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:evaluator` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `ai-feature-panel`. Preferred: `ai-feature-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Evals are tests for stochastic systems. Three-tier structure: (1) golden cases (known-correct, regression signal), (2) adversarial cases (known-bad, robustness signal), (3) free-form rubric grading (capability signal). Graders are themselves models or rules, and graders need their own validation. Thresholds matter: an eval that always passes or always fails is useless.

## First signals to inspect

- What capability is being evaluated? (Reasoning, retrieval, classification, agentic behavior)
- Existing eval framework (Inspect, Promptfoo, OpenAI evals, custom)
- Existing golden cases / labeled data
- Grader implementation (rule-based, model-based, human)
- Threshold and stability over time

## Failure modes specific to this lane

- Golden cases too easy (always passes) or too narrow (overfit)
- Grader uses the same model being evaluated (selection bias)
- Threshold set without baseline (impossible to know if a regression is real)
- Eval runs nondeterministically and 'flake' is treated as 'failure'
- No adversarial cases (system passes friendly tests, fails in production)
- Grader rubric ambiguous (different runs grade the same output differently)

## Workflow

1. Identify the capability under test and the failure modes that matter.
2. Design the three tiers: golden, adversarial, rubric.
3. Build the case set. Diversity matters more than volume initially.
4. Implement the grader. If model-based, validate the grader against human labels first.
5. Set thresholds with baseline measurement (current performance, target performance, regression threshold).
6. Wire into CI or scheduled run.
7. Document expected variance and what triggers investigation.

## Validation

Run the eval against the current system to establish baseline. Run against a known-broken version to confirm the eval catches it. Validate grader against human labels on a sample.

## Output contract

Capability Under Test | Failure Modes Targeted | Three-Tier Case Set | Grader Implementation + Validation | Baseline + Thresholds | CI Wiring | Variance Notes

## Subagent delegation

Dispatch `auditor` with focus=ai-safety for grader robustness review. See `_shared/playbooks/contract-test-patterns.md` for adjacent contract-test design.

## V4 aliases

This skill answers to V4 names: `llm-eval-design`. The router resolves them to `llm-eval-design` and notes the alias in its response.
