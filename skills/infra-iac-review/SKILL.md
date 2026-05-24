---
name: "infra-iac-review"
description: "**DEFAULT for IaC reviews — dispatches reviewer with infrastructure-as-code focus.**"
when_to_use: "Manual-only. Invoke for IaC review (Terraform, Pulumi, CloudFormation), Kubernetes manifests, Docker/compose, IAM policies, secret management, runtime config drift, or scheduled job audit. For supply-chain image provenance, use specialist `supply-chain-hardening`."
argument-hint: "[surface|module|cluster|policy]"
tier: "specialist"
aliases: ["cron-job-audit"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Infra + IaC Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `infra`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Infrastructure changes have blast radius. IAM is least-privilege by intent, often broad-privilege in practice. Secrets management has edges: rotation, access logs, blast radius of compromise. Scheduled jobs accumulate over time and silently break; audit them as a class. Drift between IaC source and actual cloud state is the silent killer.

## First signals to inspect

- IaC tool: Terraform, Pulumi, CloudFormation, Kubernetes manifests (Helm/Kustomize), Docker Compose
- Module structure and reuse (shared modules vs copy-paste)
- IAM policies: scope of permissions, principal of trust
- Secret sources: Vault, AWS SSM/Secrets Manager, Kubernetes Secrets, env files
- Scheduled jobs: cron, Kubernetes CronJob, Cloud Scheduler, GitHub Actions schedule
- State management for IaC: where is state, how is it locked, who can modify
- Drift detection: is `terraform plan` clean? Manual cloud changes?

## Failure modes specific to this lane

- IAM policies with `*` resource or `*` action 'temporarily'
- Secrets in Terraform state files (state isn't encrypted at rest)
- Kubernetes `Secret` objects not actually encrypted (they're base64, not encryption)
- Scheduled job that fails silently for months (no alerting on missed runs or failures)
- Drift: cloud has changes Terraform doesn't know about; next apply will revert them
- Container running as root, or with privileged: true, without need
- ConfigMap/Secret consumed by Pod via env var, but Pod doesn't restart on change

## Workflow

1. Identify scope: which modules, clusters, policies, jobs.
2. Audit IAM: scope each role, identify wildcards, identify cross-account trust.
3. Audit secret handling: source, rotation, access logging, blast radius.
4. Audit scheduled jobs: catalog them all, confirm alerting on failure, check last successful runs.
5. Check IaC vs reality: run `terraform plan` (or equivalent), confirm clean. Investigate drift.
6. Apply concrete fixes: tighten IAM, add alerting, fix drift.
7. For container/k8s: confirm non-root, dropped capabilities, resource limits.

## Validation

Run `terraform plan` (or equivalent) — should be clean after changes. Run any IaC test framework (terratest, kitchen-terraform). Trigger scheduled jobs in a test environment to confirm alerting fires on failure.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Scope
    type: section
    required: true
    evidence_rule: "none"
  - field: IAM Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Secret Handling Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Scheduled Job Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Drift Status
    type: section
    required: true
    evidence_rule: "none"
  - field: Container/K8s Hardening
    type: section
    required: true
    evidence_rule: "none"
  - field: Fixes Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Remaining Risks
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
```

Scope | IAM Audit | Secret Handling Audit | Scheduled Job Audit | Drift Status | Container/K8s Hardening | Fixes Applied | Remaining Risks

## Subagent delegation

Dispatch `auditor` with focus=infra for cross-cutting review. See `_shared/playbooks/cron-job-audit-checklist.md` for scheduled-job specifics.

## V4 aliases

This skill answers to V4 names: `cron-job-audit`. The router resolves them to `infra-iac-review` and notes the alias in its response.
