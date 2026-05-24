---
name: "llm-eval-design"
description: "**DEFAULT for LLM/agent eval design — dispatches evaluator for AI/LLM-specific evaluation design (offline + online metrics, groundedness, hallucination, drift, cost, latency).**"
when_to_use: "Manual-only. Invoke for eval suite design: rubrics, golden cases, graders, thresholds. For runtime safety review of an LLM system, use specialist `ai-agent-safety-review`."
argument-hint: "[system|capability|prompt under test]"
tier: "specialist"
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# LLM Eval Design

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

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

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Capability Under Test
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Failure Modes Targeted
    type: section
    required: true
    evidence_rule: "none"
  - field: Three-Tier Case Set
    type: section
    required: true
    evidence_rule: "none"
  - field: Grader Implementation + Validation
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Baseline + Thresholds
    type: section
    required: true
    evidence_rule: "none"
  - field: CI Wiring
    type: section
    required: true
    evidence_rule: "none"
  - field: Variance Notes
    type: section
    required: true
    evidence_rule: "none"
```

Capability Under Test | Failure Modes Targeted | Three-Tier Case Set | Grader Implementation + Validation | Baseline + Thresholds | CI Wiring | Variance Notes

## Subagent delegation

Dispatch `auditor` with focus=ai-safety for grader robustness review. See `_shared/playbooks/contract-test-patterns.md` for adjacent contract-test design.
