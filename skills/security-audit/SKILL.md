---
name: "security-audit"
description: "**DEFAULT for AUTH / SECRETS / INJECTION / TENANT ISOLATION — deep security review: threat model + trust-boundary audit + severity-ranked findings (Critical/High/Medium/Low) with concrete exploit sketch and fix.** Different from /review (general PR review), /supply-chain-hardening (build/publish/transitive), /dependency-audit (CVE-driven). Triggers: 'is this secure, security review, auth issue, injection check, tenant isolation, secrets handling'."
when_to_use: "Use for security-focused review of auth flows, secret handling, injection surfaces, tenant isolation, dependency security, or sensitive data handling. Kept as a core skill (auto-discoverable) because security work is too important to hide behind a flag."
argument-hint: "[surface|flow|threat|focus]"
tier: "core"
aliases: ["security-audit"]
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Security Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:security-auditor`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Apply a threat model: who is the adversary, what are they trying to do, what can they reach. Auth (who is this user?) and authorization (what can they do?) are different and both must be checked. Secrets in logs, error messages, and crash dumps are common leaks. Tenant isolation requires every query, cache, and rate-limit to scope by tenant. Trust boundaries are crossings of input from a less-trusted source to a more-trusted one — that's where validation must be explicit.

## First signals to inspect

- Auth/authorization layer: where is identity established? Where is authorization checked?
- Trust boundaries: HTTP input, deserialization, file paths, SQL, shell, eval, template rendering
- Secret handling: where are secrets read, where are they written (logs? error messages? crash dumps?)
- Tenant isolation: do all queries scope by tenant? Caches? Rate limits?
- Dependency security: known CVEs in transitive deps; install-script trust
- Sensitive log fields: PII, tokens, credentials, internal IDs

## Failure modes specific to this lane

- Auth checked at controller, authorization checked nowhere (or vice versa)
- Secrets in environment-variable error messages ('FOO_API_KEY=sk_xxx is invalid')
- Tenant ID from JWT trusted, but tenant-scoped query missing in some path
- SQL parameterization on the obvious queries; string concatenation in the cron job
- Path traversal: 'sanitization' that doesn't account for absolute paths or symlinks
- Deserializing user-controlled YAML/pickle/marshal as if it were data
- Rate limiting that doesn't bind to identity (DDoS-able, or evadable)

## Workflow

1. Identify the surface and threat model. Who, what, where.
2. Map trust boundaries. Confirm validation/escaping at each.
3. Audit auth and authorization separately. Both must succeed.
4. Scan for secret handling: env var sources, log statements, error messages, crash dumps, telemetry.
5. Scan for tenant scoping in every data access path (queries, caches, files, rate limits).
6. Audit dependency surface: known CVEs, install scripts, lockfile drift.
7. Apply high-confidence localized fixes (input validation, auth checks, secret redaction).
8. Leave policy decisions (acceptable risk, business logic) as findings.

## Validation

Add tests for the security control (e.g., 'unauthenticated request returns 401', 'cross-tenant request returns 404'). Run dependency scanner if available (npm audit, pip-audit, cargo audit). Confirm secret-redaction tests cover the new log statements.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: Threat Model
    type: section
    required: true
    evidence_rule: "STRIDE category or named attacker class"
  - field: Trust Boundaries Audited
    type: section
    required: true
    evidence_rule: "none"
  - field: Findings
    type: section
    required: true
    evidence_rule: "file:line + STRIDE/OWASP category + severity + confidence + exploit sketch"
  - field: Autonomous Fixes Applied
    type: section
    required: true
    evidence_rule: "files modified + diff summary + validation result"
  - field: Policy Decisions Surfaced
    type: section
    required: true
    evidence_rule: "rationale + alternative considered"
  - field: Validation
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Recommendations
    type: section
    required: true
    evidence_rule: "concrete action; no vague advice"
```

Threat Model | Trust Boundaries Audited | Findings (severity-ordered: Critical/High/Medium/Low + confidence) | Autonomous Fixes Applied | Policy Decisions Surfaced (Not Auto-Fixed) | Validation | Recommendations

## Subagent delegation

Dispatch `security-auditor` for an independent perspective on threat model and trust boundaries. For privacy-specific concerns, use specialist skill `data-flow-privacy-map`. For prompt-injection in AI systems, use specialist skill `ai-agent-safety-review`.

## V4 aliases

This skill answers to V4 names: `security-audit`. The router resolves them to `security-audit` and notes the alias in its response.
