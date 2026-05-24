---
name: "data-flow-privacy-map"
description: "**DEFAULT for privacy data-flow mapping: dispatches auditor with privacy + data-flow focus: runs the data-flow-privacy-map discipline.**"
when_to_use: "Manual-only. Invoke when the task is privacy-specific: data lineage, PII flows, retention, deletion/export rights, third-party sharing, or sensitive log redaction. For general security, use core `security-audit`."
argument-hint: "[surface|data type|flow]"
tier: "specialist"
aliases: ["data-flow-privacy-map", "log-redaction-pass"]
disable-model-invocation: true
output_style: "concise-review"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Data Flow + Privacy Map

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `privacy`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

PII is a property of data, not a property of variables. Track where it enters, where it flows, where it lands, where it leaves. Retention, deletion, and export rights are jurisdictional and policy-driven; the code is just the implementation. Log redaction must be enforced at the redaction layer, not at every call site (call sites forget).

## First signals to inspect

- PII inventory: what fields are PII? (names, emails, phones, addresses, IPs, IDs, free-text user content)
- Entry points: where does PII come in? (forms, APIs, third-party imports)
- Storage: databases, caches, files, message queues, logs, backups
- Egress: third-party services, exports, APIs, webhooks, analytics
- Retention configuration: per-table/per-field TTL, archival, backup retention
- Deletion/export endpoints: do they actually find all PII?
- Log statements that include user-controlled fields

## Failure modes specific to this lane

- Redacting in app logs but not in error tracker / crash dumps / metrics labels
- PII in URL query strings (gets logged everywhere)
- Cache that retains PII past the configured retention
- Backup that's outside the deletion process
- Third-party service receiving PII not covered by the privacy notice
- Free-text user content treated as non-PII when it routinely contains PII

## Workflow

1. Inventory PII fields. Confirm classification with policy if uncertain.
2. Map data flow: entry → storage → processing → egress.
3. For each storage: retention policy in place? Implementation matches?
4. For each egress: documented in privacy notice? DPA in place? Third-party retention bounded?
5. Audit logs: scan for log statements with user-controlled fields. Add redaction.
6. Validate deletion: trigger deletion in test, confirm absence in all storage layers including backups.
7. Validate export: trigger export, confirm completeness against the inventory.

## Validation

Test deletion completeness (delete request → search for residual PII). Test export completeness (export request → cross-check with inventory). Run log scanner on test fixtures with PII payloads; confirm redaction.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `concise-review` style.

```yaml
schema:
  - field: PII Inventory
    type: section
    required: true
    evidence_rule: "none"
  - field: Data Flow Map
    type: section
    required: true
    evidence_rule: "none"
  - field: Storage Retention Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Egress Audit
    type: section
    required: true
    evidence_rule: "none"
  - field: Logging Audit + Redactions Applied
    type: section
    required: true
    evidence_rule: "none"
  - field: Deletion Test Result
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Export Test Result
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Findings + Recommendations
    type: section
    required: true
    evidence_rule: "file:line citation + severity + confidence label"
```

PII Inventory | Data Flow Map | Storage Retention Audit | Egress Audit | Logging Audit + Redactions Applied | Deletion Test Result | Export Test Result | Findings + Recommendations

## Subagent delegation

Dispatch `auditor` with focus=privacy for an independent perspective. See `_shared/playbooks/log-redaction-checklist.md` for redaction patterns.

## V4 aliases

This skill answers to V4 names: `data-flow-privacy-map`, `log-redaction-pass`. The router resolves them to `data-flow-privacy-map` and notes the alias in its response.
