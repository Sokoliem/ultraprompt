#!/usr/bin/env python3
"""One-shot migration for source/skill-specs.json -> V8.6 enhancements.

What it does:
- Adds `output_schema` to every skill (derived from the pipe-delimited
  `output_contract` when not already provided). Marks every field required by
  default; evidence_rule defaults to "none" unless a per-skill override is set.
- Adds `output_style` per skill from a curated map (review/debug/etc → concise-review,
  audits → evidence-led, builders → evidence-led, planning/prd → evidence-led).
- Rewrites `description` to lead with **DEFAULT for X: …**, name competitor slash
  commands explicitly, and push trigger phrases to the end. The transformation is
  driven by parsing the existing description for "DEFAULT for/CHOICE for ..." and
  "Different from ..." fragments, falling back to a per-skill curated overlay
  when the parse misses.
- Sharpens the five "find what's missing" cluster skills' descriptions per
  recommendation #7 (gap-analysis / feature-completeness / dead-code-drift /
  test-gap-analysis / repo-review).

Idempotent: running the script twice produces the same JSON.

Run: python3 scripts/migrate-skill-specs-v8-1.py [--check]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "source" / "skill-specs.json"

# ---------------------------------------------------------------------------
# Output style assignment
# ---------------------------------------------------------------------------
# evidence-led: structured analytical work that needs claim+evidence+next.
# concise-review: severity-tagged reviewer voice with no preamble.
OUTPUT_STYLE: dict[str, str] = {
    # review-shaped work
    "review": "concise-review",
    "security-audit": "concise-review",
    "release-readiness": "concise-review",
    "repo-review": "concise-review",
    "feature-completeness": "concise-review",
    "gap-analysis": "concise-review",
    "test-gap-analysis": "concise-review",
    "dead-code-drift": "concise-review",
    "plugin-review": "concise-review",
    "accessibility-review": "concise-review",
    "database-review": "concise-review",
    "infra-iac-review": "concise-review",
    "dependency-audit": "concise-review",
    "supply-chain-hardening": "concise-review",
    "technical-debt-triage": "concise-review",
    "data-flow-privacy-map": "concise-review",
    "observability-pass": "concise-review",
    "performance-pass": "concise-review",
    "state-machine-review": "concise-review",
    "ai-agent-safety-review": "concise-review",
    "api-contract": "concise-review",
    # evidence-led for everything else (builders, debuggers, planners, prds, etc.)
}

DEFAULT_STYLE = "evidence-led"


# ---------------------------------------------------------------------------
# Evidence rule overlays per skill / per common field name
# ---------------------------------------------------------------------------
# Map field-name fragments -> evidence_rule. Conservative defaults; per-skill
# overrides win.
GENERIC_EVIDENCE_RULES: list[tuple[str, str]] = [
    ("file evidence", "file:line citation required"),
    ("file:line", "file:line citation required"),
    ("evidence", "file:line citation, command output, or doc reference required"),
    ("validation", "exact commands run + exit codes + stdout/stderr excerpts"),
    ("test", "test name + run command + result"),
    ("findings", "file:line citation + severity + confidence label"),
    ("repro", "exact command + observed output"),
    ("reproduction", "exact command + observed output"),
    ("commands", "command + exit code + excerpt"),
    ("trace", "stack trace or trace ID"),
    ("metric", "named metric + sampled value"),
    ("citation", "exact source reference"),
    ("confidence", "label: High|Medium|Low"),
    ("risk", "named risk + likelihood + impact"),
    ("recommendation", "concrete action; no vague advice"),
    ("verdict", "Approve|Approve with comments|Request changes|Needs clarification"),
    ("autonomous fix", "files modified + diff summary + validation result"),
    ("workflow", "name + entry point file:line"),
    ("schema", "type + required + example"),
    ("decision", "rationale + alternative considered"),
    ("invariant", "stated as boolean; explain what falsifies it"),
    ("dependency", "package + version + source"),
    ("threat", "STRIDE category or named attacker class"),
    ("contract", "consumer + version + breaking-change classification"),
    ("output", "schema or sample for each format"),
]

# Per-skill explicit evidence-rule overlays (key = lowercased section name fragment)
PER_SKILL_EVIDENCE: dict[str, dict[str, str]] = {
    "debug": {
        "root cause": "file:line + minimal reproduction + falsifiable hypothesis",
        "fix summary": "files modified + scope justification",
        "regression test added": "test name + command + before/after result",
    },
    "ci-repair": {
        "failure layer": "log excerpt that proves the layer",
        "fix": "diff summary + green run command",
    },
    "security-audit": {
        "findings": "file:line + STRIDE/OWASP category + severity + confidence + exploit sketch",
    },
    "release-readiness": {
        "blockers": "file:line or system reference + why it blocks",
    },
}


# ---------------------------------------------------------------------------
# Description rewrite
# ---------------------------------------------------------------------------

TRIGGER_PHRASE_RE = re.compile(r"When user says\s+'([^']+)'\s*\W+")
DEFAULT_CLAIM_RE = re.compile(r"DEFAULT(?:\s+CHOICE)?\s+(?:for|on)\s+([^.]+?)\.", re.IGNORECASE)
DIFFERENT_FROM_RE = re.compile(r"Different from\s+(.+?)(?:$)", re.IGNORECASE | re.DOTALL)
PRODUCES_RE = re.compile(r"—\s*(.+?)\.", re.DOTALL)


def parse_description(desc: str) -> dict[str, str]:
    """Best-effort parse of the current description format into parts."""
    out: dict[str, str] = {"raw": desc}
    m = TRIGGER_PHRASE_RE.search(desc)
    if m:
        out["triggers"] = m.group(1).strip()
    m = DEFAULT_CLAIM_RE.search(desc)
    if m:
        out["default_for"] = m.group(1).strip()
    m = DIFFERENT_FROM_RE.search(desc)
    if m:
        out["different_from"] = m.group(1).strip().rstrip(".") + "."
    m = PRODUCES_RE.search(desc)
    if m:
        out["produces"] = m.group(1).strip()
    return out


def resolve_description_meta(spec: dict[str, Any], override: dict[str, str] | None) -> dict[str, str]:
    """Build the canonical description components for this spec.

    Persisted into `spec["description_meta"]` so subsequent runs of this
    migration are idempotent and the description can always be regenerated
    from the same source. Precedence:

    1. Per-skill curated `override` (when defined in DESCRIPTION_OVERRIDES).
    2. Previously persisted `spec["description_meta"]` (from an earlier run).
    3. Best-effort parse of the legacy description.
    """
    override = override or {}
    parsed = parse_description(spec.get("description", ""))
    prior = spec.get("description_meta") or {}

    def pick(key: str, default: str) -> str:
        return (
            override.get(key)
            or prior.get(key)
            or parsed.get(key)
            or default
        )

    meta = {
        "default_for": pick("default_for", spec["name"]),
        "produces": pick("produces", f"runs the {spec['name']} discipline"),
        "different_from": pick("different_from", ""),
        "triggers": pick("triggers", ""),
    }
    if len(meta["produces"]) > 220:
        meta["produces"] = meta["produces"][:217].rstrip() + "..."
    return meta


def render_description(meta: dict[str, str]) -> str:
    parts: list[str] = [f"**DEFAULT for {meta['default_for']}: {meta['produces']}.**"]
    if meta["different_from"]:
        different_from = meta["different_from"].rstrip()
        if not different_from.endswith("."):
            different_from += "."
        parts.append(f"Different from {different_from}")
    if meta["triggers"]:
        parts.append(f"Triggers: '{meta['triggers']}'.")
    return " ".join(parts)


# Per-skill curated overrides for descriptions. The 5 de-collision cluster
# skills (#7) and the most-frequently confused skills get explicit overrides
# so they sharpen lanes and call out siblings by name.
DESCRIPTION_OVERRIDES: dict[str, dict[str, str]] = {
    # --- #7 de-collision cluster -----------------------------------------
    "gap-analysis": {
        "default_for": (
            "TARGETED gap analysis on ONE NAMED FEATURE end-to-end (frontend/backend/data/tests/docs)"
        ),
        "produces": (
            "front-door for the gap-analysis cluster: orchestrates feature-completeness-auditor + "
            "wiring-gap-inspector and synthesizes confirmed/likely gaps with file:line evidence"
        ),
        "different_from": (
            "/repo-review (WHOLE-REPO audit, not one feature), /feature-completeness (auditor only, "
            "no orchestration), /test-gap-analysis (missing TESTS only), and /dead-code-drift "
            "(unused/stale code only). NOT THIS skill if your scope is the whole repo, only the test "
            "surface, or only dead code."
        ),
        "triggers": (
            "gap analysis on <feature>, what's missing in <feature>, end-to-end audit of <feature>, "
            "is <feature> done"
        ),
    },
    "feature-completeness": {
        "default_for": (
            "AUDITOR-ONLY single-feature completeness check (when you already know which feature "
            "and do not want orchestration)"
        ),
        "produces": (
            "structured completeness audit for one feature with confirmed/likely/missing controls "
            "and file:line evidence; no cross-feature orchestration"
        ),
        "different_from": (
            "/gap-analysis (orchestrates this auditor + wiring-gap-inspector — use that for cross-cutting "
            "feature gaps), /repo-review (whole repo), /test-gap-analysis (missing tests only)."
        ),
        "triggers": (
            "is <feature> complete, audit <feature> for completeness, does <feature> handle <case>"
        ),
    },
    "dead-code-drift": {
        "default_for": (
            "UNUSED, STALE, OR DRIFTED CODE ONLY — exports/imports/configs/migrations/fixtures with no "
            "live reference"
        ),
        "produces": (
            "ranked drift findings (safe-to-remove vs needs-review) with reference evidence and quick wins"
        ),
        "different_from": (
            "/gap-analysis (missing features, not unused code), /feature-completeness (single-feature "
            "completeness), /technical-debt-triage (debt with risk×leverage scoring, not drift), "
            "/repo-review (whole-repo audit)."
        ),
        "triggers": (
            "dead code, unused exports, stale fixtures, drift, what can we delete"
        ),
    },
    "test-gap-analysis": {
        "default_for": (
            "MISSING TEST COVERAGE ONLY — uncovered behaviors, lanes, boundary cases, and risky paths "
            "without tests"
        ),
        "produces": (
            "risk-weighted list of missing test coverage with critical lanes, missing test types, and "
            "regression-test priorities"
        ),
        "different_from": (
            "/test-harden (WRITE the missing tests — use this AFTER test-gap-analysis), "
            "/gap-analysis (whole-feature gaps incl. wiring/docs), /feature-completeness (single-feature "
            "completeness)."
        ),
        "triggers": (
            "missing test coverage, untested paths, what needs a test, where are we test-blind"
        ),
    },
    "repo-review": {
        "default_for": (
            "WHOLE-REPO end-to-end audit (map + gaps + drift + test gaps + release readiness in one pass)"
        ),
        "produces": (
            "structured repo review covering map, confirmed gaps, probable gaps, test gaps, contract drift, "
            "stale code, release readiness, top risks, quick wins, and implementation sequence — V8 "
            "panel-ready"
        ),
        "different_from": (
            "/gap-analysis (ONE feature end-to-end), /feature-completeness (single feature), "
            "/dead-code-drift (drift only), /test-gap-analysis (tests only), /release-readiness "
            "(ship/no-ship gate only)."
        ),
        "triggers": (
            "audit the codebase, review the whole repo, what's incomplete across the repo, "
            "is this ready to ship overall, comprehensive repo audit"
        ),
    },
    # --- The big "default builder" so it competes with anthropic builts ---
    "build": {
        "default_for": (
            "WRITING NEW CODE — minimum-diff implementation with explicit tests + claim-check before "
            "declaring success"
        ),
        "produces": (
            "feature-scoped implementation with files-changed, tests-added, validation-runs, and a "
            "claim-check result; dispatches to the ultraprompt:builder agent for multi-file scope and "
            "stays inline for single-function tweaks"
        ),
        "different_from": (
            "/refactor (behavior-preserving cleanup — no new feature), /migrate (intentional breaking "
            "change with migration plan), anthropic-skills:frontend-studio (UI design artifact, not code), "
            "anthropic-skills:plan-mode (plans, not implementations)."
        ),
        "triggers": (
            "build this, implement <feature>, write the code for <X>, scaffold this, add a function that <Y>, "
            "create the feature, make a new component"
        ),
    },
    "refactor": {
        "default_for": (
            "BEHAVIOR-PRESERVING cleanup — restructure existing code without changing observable behavior"
        ),
        "produces": (
            "refactor plan + diffs that preserve invariants, with before/after test parity and a behavior-"
            "invariants checklist"
        ),
        "different_from": (
            "/build (NEW feature/behavior), /migrate (intentional breaking change), /technical-debt-triage "
            "(picks WHAT to refactor)."
        ),
        "triggers": (
            "refactor this, clean this up without changing behavior, extract this, rename across the codebase"
        ),
    },
    "migrate": {
        "default_for": (
            "INTENTIONAL BREAKING CHANGE with explicit migration plan (data, API, or framework)"
        ),
        "produces": (
            "phased migration with pre/action/validate/rollback per step and consumer notification plan"
        ),
        "different_from": (
            "/refactor (NO behavior change), /build (no migration of existing state/API), /database-review "
            "(reviews DB changes but does not own the sequence)."
        ),
        "triggers": (
            "migrate <X> to <Y>, breaking change rollout, deprecate <thing>, upgrade <framework>"
        ),
    },
    "review": {
        "default_for": "DIFF/PR REVIEW — produces structured findings with severity and merge verdict",
        "produces": (
            "PR understanding + severity-ranked findings (correctness/design/safety/maintainability/"
            "consistency) + merge verdict; --deep fans out to a panel for parallel perspectives"
        ),
        "different_from": (
            "/repo-review (whole-repo audit, not one diff), /security-audit (security depth only), "
            "/release-readiness (ship/no-ship gate, not line-level review)."
        ),
        "triggers": (
            "review this PR, code review, check this diff, look at these changes, before-merge review"
        ),
    },
    "debug": {
        "default_for": "ACTIVE FAILURE DIAGNOSIS — symptom → reproduction → falsifiable root cause",
        "produces": (
            "captured failure signature, smallest reproduction, bisection trail, root-cause hypothesis "
            "with confidence label, and same-bug-elsewhere search"
        ),
        "different_from": (
            "/test-gap-analysis (finds missing tests, not broken behavior), /review (PR scope), "
            "/ci-repair (pipeline-shape failures: matrix, env, cache)."
        ),
        "triggers": (
            "this is failing, why is X broken, reproduce the error, debug this, failing test, runtime error"
        ),
    },
    "ci-repair": {
        "default_for": "BUILD/LINT/TYPECHECK/PIPELINE FAILURE — fix the pipeline, not the symptom",
        "produces": (
            "layered failure analysis (workflow|cache|deps|env|code), last-successful-run diff, fix, "
            "and green-run command"
        ),
        "different_from": (
            "/debug (runtime/test failures in code), /dependency-audit (CVE-driven, not failure-driven), "
            "/release (release notes, not pipeline repair)."
        ),
        "triggers": (
            "CI is red, pipeline broken, build is failing, lint failure, typecheck failure, cache miss"
        ),
    },
    "test-harden": {
        "default_for": "WRITING OR STRENGTHENING TESTS — author missing tests with behavior contracts",
        "produces": (
            "coverage-targeted test additions with behavior contracts, boundary cases, and removed "
            "change-detector tests"
        ),
        "different_from": (
            "/test-gap-analysis (FINDS missing tests — run first), /debug (fix the bug, not add coverage), "
            "/build (new feature code, not test code)."
        ),
        "triggers": (
            "write tests for <X>, add coverage for <Y>, strengthen these tests, harden the test suite"
        ),
    },
    "architect": {
        "default_for": "ARCHITECTURAL QUESTIONS — boundaries, contracts, and system design with tradeoffs",
        "produces": (
            "architectural question framing + current vs intended shape + gaps + cost-assessment with "
            "recommendation"
        ),
        "different_from": (
            "/build (implements the architecture), /review (PR-scope), /repo-review (whole-repo audit "
            "without design recommendation)."
        ),
        "triggers": (
            "should we use X or Y, how should we structure this, design tradeoffs, system boundaries"
        ),
    },
    "security-audit": {
        "default_for": "AUTH / SECRETS / INJECTION / TENANT ISOLATION — deep security review",
        "produces": (
            "threat model + trust-boundary audit + severity-ranked findings (Critical/High/Medium/Low) "
            "with concrete exploit sketch and fix"
        ),
        "different_from": (
            "/review (general PR review), /supply-chain-hardening (build/publish/transitive), "
            "/dependency-audit (CVE-driven)."
        ),
        "triggers": (
            "is this secure, security review, auth issue, injection check, tenant isolation, secrets handling"
        ),
    },
    "repo-map": {
        "default_for": (
            "REPO DISCOVERY & CODE LOCATION — structured read-only repo contract you cache before any "
            "implementation, review, onboarding, or planning work"
        ),
        "produces": (
            "cached read-only repo contract: architecture, packages, workflows, validation commands, "
            "conventions, dependencies, ownership, sensitive paths, recent activity, plus `--semantic` "
            "code search for finding code by behavior or natural-language concept"
        ),
        "different_from": (
            "/repo-review (audits the whole repo, this maps it), /architect (design decisions, not "
            "discovery), built-in Explore (unstructured tour without caching or validation-command surfacing)."
        ),
        "triggers": (
            "find code that does X, where is the code for Y, find the handler for Z, locate the function "
            "that handles W, code search, semantic search, onboarding to this repo, give me a repo map, "
            "what's in this repo, how is this repo organized"
        ),
    },
    "prd-ai-feature": {
        "default_for": (
            "PRD FOR AN AI/LLM/AGENT FEATURE — model selection rationale, eval plan, safety boundaries, "
            "cost envelope, failure-mode map"
        ),
        "produces": (
            "PRD covering AI-specific sections (model selection, eval design, safety boundaries, cost "
            "envelope, failure-mode map) on top of the standard PRD shape"
        ),
        "different_from": (
            "/prd-standard (non-AI features), /prd-technical (deep tech-design PRD, not AI-specific), "
            "/llm-eval-design (eval design only)."
        ),
        "triggers": (
            "PRD for an AI feature, AI-feature spec, agent feature PRD, LLM feature spec, model-backed feature"
        ),
    },
}


# ---------------------------------------------------------------------------
# Output schema derivation
# ---------------------------------------------------------------------------

PIPE_SPLIT_RE = re.compile(r"\s+\|\s+|\s*\|\s*")


def normalize_field(s: str) -> str:
    s = s.strip()
    # Drop trailing parenthetical hints from the section name so the field
    # remains stable.
    s = re.sub(r"\s*\(.*$", "", s)
    return s.strip()


def evidence_rule_for(field: str, skill_name: str) -> str:
    low = field.lower()
    per = PER_SKILL_EVIDENCE.get(skill_name, {})
    for key, rule in per.items():
        if key in low:
            return rule
    for key, rule in GENERIC_EVIDENCE_RULES:
        if key in low:
            return rule
    return "none"


def derive_output_schema(spec: dict[str, Any]) -> list[dict[str, Any]]:
    if spec.get("output_schema"):
        return spec["output_schema"]
    contract = spec.get("output_contract", "") or ""
    if not contract:
        return []
    raw_fields = [normalize_field(p) for p in PIPE_SPLIT_RE.split(contract) if p.strip()]
    schema: list[dict[str, Any]] = []
    name = spec["name"]
    seen: set[str] = set()
    for field in raw_fields:
        if not field:
            continue
        key = field.lower()
        if key in seen:
            continue
        seen.add(key)
        entry: dict[str, Any] = {
            "field": field,
            "type": "section",
            "required": True,
            "evidence_rule": evidence_rule_for(field, name),
        }
        schema.append(entry)
    return schema


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------


def migrate(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for spec in specs:
        name = spec["name"]
        # output_schema (derive-from-pipe-contract only when not already set)
        spec["output_schema"] = derive_output_schema(spec)
        # output_style
        spec["output_style"] = OUTPUT_STYLE.get(name, DEFAULT_STYLE)
        # description: persist canonical components and regenerate from them
        override = DESCRIPTION_OVERRIDES.get(name)
        meta = resolve_description_meta(spec, override)
        spec["description_meta"] = meta
        spec["description"] = render_description(meta)
    return specs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    new = migrate(json.loads(json.dumps(specs)))  # deep copy
    new_text = json.dumps(new, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        current = SPECS.read_text(encoding="utf-8")
        if current != new_text:
            print("DRIFT: skill-specs.json differs from migration output.", file=sys.stderr)
            return 1
        print("skill-specs.json matches migration output.")
        return 0
    SPECS.write_text(new_text, encoding="utf-8")
    print(f"Migrated {len(new)} skills in {SPECS.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
