---
name: "ci-repair"
description: "**DEFAULT for BUILD/LINT/TYPECHECK/PIPELINE FAILURE — fix the pipeline, not the symptom: layered failure analysis (workflow|cache|deps|env|code), last-successful-run diff, fix, and green-run command.** Different from /debug (runtime/test failures in code), /dependency-audit (CVE-driven, not failure-driven), /release (release notes, not pipeline repair). Triggers: 'CI is red, pipeline broken, build is failing, lint failure, typecheck failure, cache miss'."
when_to_use: "Use when the failure is in the pipeline (matrix, cache, env, dependencies, runner image, workflow file) rather than the code under test. If the same test fails locally, use `debug` instead. If the failure mode is non-determinism, use `debug --flaky`."
argument-hint: "[workflow|job|step name|error excerpt]"
tier: "core"
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# CI Repair

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:debugger` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

CI failures decompose into: (1) pipeline configuration (workflow YAML, matrix, runner image, env vars, secrets), (2) caching (stale, missing, key drift), (3) dependency state (lockfile mismatch, registry availability, transitive breakage), (4) environment drift (CI runner has different versions or tools than developer machines), (5) actual code bug exposed only in CI. Diagnose the layer before changing code.

## First signals to inspect

- Failing job name, step name, and the actual error (not just 'CI failed')
- Workflow file under `.github/workflows/`, `.gitlab-ci.yml`, `circleci/config.yml`, etc.
- Last successful run on the same branch or main; what changed between then and now
- Lockfile vs. manifest consistency (npm ci vs npm install; pnpm install --frozen-lockfile)
- Cache hit/miss in the failing run (most CI providers log this)
- Runner image version, tool versions installed, env vars set

## Failure modes specific to this lane

- Adding `|| true` or `continue-on-error` to make the job green without fixing the cause
- Increasing timeouts when the real issue is a hung process
- Bumping a dependency to make it pass in CI when the local lockfile would have caught the issue
- Editing the workflow to skip the failing test rather than fixing the test
- Treating cache misses as the cause when the issue is upstream

## Workflow

1. Identify the layer: workflow config / cache / deps / env drift / actual code.
2. Read the failing run's logs for the actual error.
3. Check the last successful run and diff what changed.
4. If the failure reproduces locally with CI's exact command, hand off to `debug`.
5. If pipeline-specific, fix at the right layer: workflow YAML, lockfile reset, cache key bump, runner image pin, env var.
6. Re-run the failing job locally if the runner image is reproducible (act, docker).
7. Validate by running the workflow's exact command sequence locally where possible.

## Validation

Reproduce the failing step locally with the same command and env. If using GitHub Actions, `act` can run jobs locally. After fixing, watch the CI run end-to-end on a branch before merging.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Failure Layer
    type: section
    required: true
    evidence_rule: "log excerpt that proves the layer"
  - field: cache
    type: section
    required: true
    evidence_rule: "none"
  - field: deps
    type: section
    required: true
    evidence_rule: "none"
  - field: env
    type: section
    required: true
    evidence_rule: "none"
  - field: code)
    type: section
    required: true
    evidence_rule: "none"
  - field: Evidence
    type: section
    required: true
    evidence_rule: "file:line citation, command output, or doc reference required"
  - field: Last Successful Run Comparison
    type: section
    required: true
    evidence_rule: "none"
  - field: Fix
    type: section
    required: true
    evidence_rule: "diff summary + green run command"
  - field: Why Not a Code Bug
    type: section
    required: true
    evidence_rule: "none"
  - field: Local Reproduction
    type: section
    required: true
    evidence_rule: "exact command + observed output"
  - field: Remaining Risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
```

Failure Layer (workflow|cache|deps|env|code) | Evidence | Last Successful Run Comparison | Fix (file + lines) | Why Not a Code Bug | Local Reproduction | Remaining Risks (e.g., 'cache key change will force one slow rebuild')

## Subagent delegation

Dispatch `auditor` with focus=infra for cross-pipeline patterns. For deep CI matrix optimization, see `_shared/playbooks/build-test-optimizer.md`.
