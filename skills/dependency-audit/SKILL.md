---
name: "dependency-audit"
description: "**DEFAULT for dependency/supply-chain audits: dispatches auditor with supply-chain focus: runs the dependency-audit discipline.**"
when_to_use: "Manual-only. Invoke for dep-focused review: CVE scan, transitive analysis, license audit, abandonment risk. For supply-chain provenance and CI trust, use specialist `supply-chain-hardening`. For upgrade planning, use core `migrate --deps`."
argument-hint: "[ecosystem|focus]"
tier: "specialist"
aliases: ["dependency-audit"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Dependency Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `dependencies`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Direct dependency count is small; transitive count is what matters. Known-CVE scanning is necessary but not sufficient: also check abandonment (last commit, maintainer count), license drift (transitive GPL where MIT was promised), and version drift (multiple versions of the same package in the tree).

## First signals to inspect

- Lockfile (package-lock.json, pnpm-lock.yaml, yarn.lock, Cargo.lock, go.sum, requirements.lock)
- Direct vs transitive count (npm ls --all | wc -l, pnpm list --depth Infinity)
- Known-CVE scanner output (npm audit, pnpm audit, pip-audit, cargo audit, snyk, OSV)
- Last commit date and contributor count for direct deps
- License of every transitive dep (license-checker, cargo-deny, go-licenses)
- Multiple versions of the same package in the tree (often a sign of conflicting peer requirements)

## Failure modes specific to this lane

- Running scanner once and not gating CI on it
- Treating 'no known CVE' as 'safe' (zero-days exist; abandoned deps don't get CVEs filed)
- Ignoring transitive license risk because direct license is fine
- Multiple versions of a security-sensitive package (auth, crypto, parsing) coexisting
- Auto-updating without testing

## Workflow

1. Inventory: direct vs transitive count; ecosystem.
2. Run known-CVE scanner. Triage by severity and exposure (is the vulnerable code path reachable?).
3. Check abandonment risk for direct deps: last commit, contributor count, recent activity.
4. License audit: confirm transitive licenses match policy.
5. Identify version-drift cases (multiple versions of same package). Assess if they matter.
6. Produce a risk-ordered finding list with concrete remediation per item.

## Validation

Re-run scanner after remediation. For upgrades: run full test matrix. For removed deps: confirm no remaining usage.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Dep Inventory
    type: section
    required: true
    evidence_rule: "none"
  - field: CVE Findings
    type: section
    required: true
    evidence_rule: "file:line citation + severity + confidence label"
  - field: Abandonment Risk
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
  - field: License Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Version Drift
    type: section
    required: true
    evidence_rule: "none"
  - field: Risk-Ordered Recommendations
    type: section
    required: true
    evidence_rule: "named risk + likelihood + impact"
```

Dep Inventory (direct + transitive count) | CVE Findings (severity, exposure, remediation) | Abandonment Risk (per direct dep) | License Audit | Version Drift | Risk-Ordered Recommendations

## Subagent delegation

Dispatch `auditor` with focus=dependencies. For provenance and supply-chain trust, dispatch specialist `supply-chain-hardening`.

## V4 aliases

This skill answers to V4 names: `dependency-audit`. The router resolves them to `dependency-audit` and notes the alias in its response.
