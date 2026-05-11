---
name: "observability-pass"
description: "When user says 'observability audit / logging review / metrics review / tracing audit / monitoring gaps / SLO design / observability gaps' — dispatches auditor with observability focus. DEFAULT for observability-specific audits."
when_to_use: "Manual-only. Invoke for observability gaps: insufficient logs, missing metrics, broken traces, ineffective alerting, or SLO design. For incident reconstruction, see `_shared/playbooks/incident-postmortem-template.md`."
argument-hint: "[surface|operation|signal]"
tier: "specialist"
aliases: ["observability-pass"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Observability Pass

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `observability`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Observability is for the unknown unknown: logs, metrics, and traces should help diagnose problems you didn't predict. The signals must be high-cardinality enough to find specific cases but low-cardinality enough to be cheap to query. Alerting should fire on user impact, not on infrastructure proxies (CPU is not a symptom).

## First signals to inspect

- Logging library and conventions (structured? levels? sampling?)
- Metrics library and conventions (Prometheus, OpenTelemetry, vendor SDK)
- Tracing: enabled? Sampled? Spans cover what?
- Error reporting: Sentry/Bugsnag/Honeybadger integration; what's captured
- Alerts: what fires? What's signal vs noise?
- SLOs: defined? Measured? Reported?
- Dashboards: do they answer 'is the system healthy?' in <30 seconds?

## Failure modes specific to this lane

- Logs without structure (string interpolation; can't filter)
- Metrics with high-cardinality labels (user_id) blowing up cost
- Traces that stop at the service boundary (no propagation)
- Alerts on infrastructure (CPU > 80%) instead of user impact (latency p99 > SLO)
- Error reporting that swallows the stack trace
- SLO measured but not budgeted (no error budget concept)
- Logging PII (see also data-flow-privacy-map for redaction)

## Workflow

1. Identify the operation/surface and what 'observable' should mean for it.
2. Audit log statements: structure, level, fields, sensitive content.
3. Audit metrics: relevant, low-cardinality, units, labels.
4. Audit traces: span coverage, propagation across services.
5. Audit alerts: fire on user impact, not on proxies.
6. Audit SLO/error budget if applicable.
7. Apply fixes: add structure to logs, add missing metrics, fix span propagation, retune alerts.

## Validation

Trigger the operation; confirm logs/metrics/traces appear as expected. Trigger known-failure scenarios; confirm alerts fire. Check dashboard answers 'is it healthy?' in 30s.

## Output contract

Scope | Logging Audit + Fixes | Metrics Audit + Fixes | Tracing Audit + Fixes | Alerting Audit + Retunes | SLO Status | Dashboard Quality | Remaining Gaps

## Subagent delegation

Dispatch `auditor` with focus=observability.

## V4 aliases

This skill answers to V4 names: `observability-pass`. The router resolves them to `observability-pass` and notes the alias in its response.
