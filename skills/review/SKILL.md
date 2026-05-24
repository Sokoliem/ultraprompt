---
name: "review"
description: "**DEFAULT for DIFF/PR REVIEW — produces structured findings with severity and merge verdict: PR understanding + severity-ranked findings (correctness/design/safety/maintainability/consistency) + merge verdict; --deep fans out to a panel for parallel perspectives.** Different from /repo-review (whole-repo audit, not one diff), /security-audit (security depth only), /release-readiness (ship/no-ship gate, not line-level review). Triggers: 'review this PR, code review, check this diff, look at these changes, before-merge review'."
when_to_use: "Use for diff/branch/PR review. Use `--deep` for cross-cutting risk requiring multi-perspective review (invokes panel-run review-fanout). Use `--summarize` for PR summary or release-note blurb only. Do not use for non-diff architecture work (use architect) or for failing tests (use debug)."
argument-hint: "[PR|branch|diff|path|--deep|--summarize]"
tier: "core"
aliases: ["pr-review", "pr-summarize", "coverage-impact", "agentic-deep-review"]
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus derived from `$ARGUMENTS`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Diff-correctness and merge readiness. Evaluate the change in the context of what it touches: call sites, tests, docs, generated files, dependency manifests. Classify by severity (Blocker, Major, Minor, Nit) and confidence (High, Medium, Low). Apply autonomous fixes only for high-confidence issues with localized scope.

## First signals to inspect

- git status, git branch --show-current, git merge-base HEAD origin/main
- git diff --stat --find-renames <base>...HEAD
- git diff --name-status --find-renames <base>...HEAD
- gh pr view --json number,title,body,baseRefName,headRefName,files,commits when GitHub CLI is available
- Tests adjacent to changed files; type-check and lint config
- Coverage of changed lines (--summarize / coverage analysis is part of the default workflow)

## Failure modes specific to this lane

- Approving without checking call sites of changed exports
- Missing breaking-change implications in config, migrations, or wire formats
- Treating green CI as evidence the change is correct (CI may not exercise the affected path)
- Recommending broad refactors during review (out of scope; capture as follow-ups)
- Confusing 'tests pass after my fix' with 'fix is durable' when the test is the same one that exposed the bug

## Workflow

1. Identify base, head, and intent of the change. Use `$ARGUMENTS` if supplied.
2. Inspect changed lines + immediate context: surrounding code, call sites, tests, configs, docs, generated files, manifests/lockfiles.
3. Classify findings (severity x confidence). Mark which are autonomously fixable.
4. Apply only high-confidence localized fixes per autonomous-fix policy in DISCIPLINE.md.
5. Add or update regression tests for fixed behavior when appropriate.
6. Run focused validation first, then broader validation when practical.
7. If `--deep` was passed, invoke `panel-run review-fanout` for parallel security/perf/architecture/tests perspectives and synthesize findings.
8. Re-review the final diff. Produce merge recommendation.

## Validation

Targeted tests for affected behavior, then type-check/lint, then broader suite. Cite exact commands and results. If a needed validation cannot be run, name it.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: PR Understanding
    type: section
    required: true
    evidence_rule: "none"
  - field: Autonomous Fix Summary
    type: section
    required: true
    evidence_rule: "files modified + diff summary + validation result"
  - field: Merge Recommendation
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
  - field: Risk Assessment
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: Remaining Findings
    type: section
    required: true
    evidence_rule: "file:line citation + severity + confidence label"
  - field: Validation Performed
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Final Diff Summary
    type: section
    required: true
    evidence_rule: "none"
  - field: Questions/Follow-Ups
    type: section
    required: true
    evidence_rule: "none"
```

PR Understanding | Autonomous Fix Summary (table when multiple) | Merge Recommendation (Approve / Approve with minor comments / Request changes / Needs clarification) | Risk Assessment (correctness/compat/security/perf/coverage/ops/maintainability) | Remaining Findings (severity-ordered) | Validation Performed | Final Diff Summary | Questions/Follow-Ups

## Subagent delegation

For non-trivial diffs, dispatch `reviewer` with focus parameters (code, security, tests, api, performance) as warranted. Use `panel-run review-fanout` when independent parallel perspectives reduce risk.

## V4 aliases

This skill answers to V4 names: `pr-review`, `pr-summarize`, `coverage-impact`, `agentic-deep-review`. The router resolves them to `review` and notes the alias in its response.
