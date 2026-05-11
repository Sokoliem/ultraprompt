---
name: "release-readiness"
description: "When user says 'is this ready to ship / release readiness / ship/no-ship / can we deploy / pre-release audit / production-ready check / what's blocking release' — produces ready/risky/blocked verdict with blockers, warnings, missing controls, and recommended release sequence. DEFAULT for shipability assessment. Different from release (writes notes/changelog) — release-readiness audits whether the codebase is shippable."
when_to_use: "When the user wants a ship/no-ship verdict with blockers and remediation sequence."
argument-hint: "[optional: target environment or release version]"
tier: "core"
aliases: ["ship-readiness", "release-check", "production-audit"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Release Readiness Audit

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:release-readiness-auditor`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Release-readiness assesses shipability; release writes release notes; release-scorecard (MCP tool) checks plugin itself. Use release-readiness for product code release gating.

## First signals to inspect

- User is approaching a release milestone.
- User asks 'are we good to ship'.
- User wants gating criteria before deploy.

## Failure modes specific to this lane

- Requiring enterprise controls for alpha projects.
- Missing critical migration safety checks.
- Producing generic best-practice warnings without evidence.
- Conflating warnings with blockers.

## Workflow

1. Dispatch release-readiness-auditor.
2. Auditor produces ready/risky/blocked verdict + structured findings.
3. Synthesize for the user: clear ship-or-not call with justification.
4. Order remediation: blockers first, then critical warnings, then warnings.
5. After synthesis, persist findings to the gap ledger via the `gap_ledger_write` MCP tool: ONE call per gap with required fields (repo, title, category, severity, confidence, evidence, recommended_fix). Auto-skip if --no-ledger argument supplied. Print the gap IDs assigned (e.g., GAP-celestial-0042) for user reference. Before writing, optionally call `gap_ledger_query` with the same repo to detect duplicates from prior sessions — if a similar gap exists, update its evidence rather than create new.
6. End with: gate criteria for each phase + validation commands.

## Validation

Every blocker and warning must cite file:line evidence (or absence-of-file). Verdict follows verdict rules: 0 blockers + acceptable warnings = ready; 0 blockers + many warnings = risky; ≥1 blocker = blocked.

## Output contract

Verdict (ready/risky/blocked) | Blockers with evidence | Warnings ranked | Missing operational controls | Required validation commands | Rollback concerns | Phased release sequence with gate criteria

## Subagent delegation

Default: dispatch release-readiness-auditor. For deep follow-up: dispatch security-auditor (if secrets handling flagged) + test-strategist (if test gaps flagged).

## V4 aliases

This skill answers to V4 names: `ship-readiness`, `release-check`, `production-audit`. The router resolves them to `release-readiness` and notes the alias in its response.
