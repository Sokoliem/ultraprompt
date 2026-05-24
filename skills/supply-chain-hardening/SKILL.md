---
name: "supply-chain-hardening"
description: "**DEFAULT for supply-chain hardening work — dispatches security-auditor + auditor with supply-chain focus.**"
when_to_use: "Manual-only. Invoke for supply-chain integrity work: lockfile hygiene, install-script trust, CI publishing pipeline, SBOM generation, container image provenance, registry trust. For dep CVEs/abandonment, use specialist `dependency-audit`."
argument-hint: "[surface|pipeline]"
tier: "specialist"
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Supply Chain Hardening

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `supply-chain`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Supply chain attacks happen at install time and publish time, not just at consume time. Untrusted install scripts run with full developer or CI privilege. The CI pipeline that publishes packages is itself a high-value target. Lockfiles bind versions but not contents (without integrity hashes). SBOMs are a record, not a control.

## First signals to inspect

- Lockfile presence and integrity hashes (sha512 in npm, hash in Cargo.lock, go.sum)
- Install scripts in dependencies (npm postinstall, pip setup.py, gem extconf)
- CI publishing pipeline: who can publish? Where do credentials come from?
- Container base images: pinned by digest (sha256), or by tag (mutable)?
- Registry/repository configuration: which registries does the build pull from?
- SBOM generation in CI
- Signed commits, signed tags, signed releases

## Failure modes specific to this lane

- Install scripts running unreviewed code from transitive deps
- CI uses a long-lived deploy token instead of OIDC short-lived credentials
- Container image pinned by tag (`:latest` or `:v1.0`) — mutable
- Lockfile committed but `npm install` used in CI instead of `npm ci` (lockfile not enforced)
- Publishing pipeline triggered by tag, but tag-creation isn't gated
- SBOM generated but not stored alongside the artifact

## Workflow

1. Audit lockfile: present, integrity hashes, enforced in CI (npm ci / pnpm install --frozen-lockfile / pip install --require-hashes).
2. Audit install scripts: list them, review what they do, consider --ignore-scripts for low-risk deps.
3. Audit CI publishing: who, when, with what credentials, gated by what.
4. Audit container builds: base image pinned by digest? Builder image trusted? Multi-stage to reduce attack surface?
5. Generate SBOM (CycloneDX or SPDX) and store with each release artifact.
6. Sign commits/tags/releases if not already.
7. Apply concrete hardening: digest-pin images, add `npm ci`, switch CI to OIDC, gate publishing.

## Validation

Run the CI pipeline end-to-end after hardening. Verify SBOM is generated and contains expected components. Verify image digests are reproducible.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Lockfile Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Install-Script Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: CI Publishing Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Container Image Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: SBOM Status
    type: section
    required: true
    evidence_rule: "none"
  - field: Signing Status
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

Lockfile Audit | Install-Script Audit | CI Publishing Audit | Container Image Audit | SBOM Status | Signing Status | Hardenings Applied | Remaining Risks

## Subagent delegation

Dispatch `auditor` with focus=supply-chain. For container-specific concerns, dispatch `auditor` with focus=infra.
