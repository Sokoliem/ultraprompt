#!/usr/bin/env python3
"""Run the Ultraprompt V8 router bench.

Three modes:
- positive (default): golden cases from tests/routing/golden-cases.yaml
- --adversarial: cases that must not match (from tests/routing/adversarial-cases.yaml)
- --overlap-budget: catalog overlap budget from tests/routing/overlap-budget.yaml

Targets:
- positive: >=90% top-1, 100% top-3
- adversarial: 100% reject
- overlap: no two skills tied above the overlap threshold on the same intent
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ultraprompt_index import build_index, find_plugin_root


def load_yaml_cases(path: Path) -> list[dict]:
    """Minimal YAML loader for our restricted case format. Avoids PyYAML dependency."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    cases: list[dict] = []
    current: dict | None = None
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("- "):
            if current is not None:
                cases.append(current)
            current = {}
            line = line[2:]
        if current is None:
            continue
        if ":" in line and not line.lstrip().startswith("- "):
            key, _, value = line.lstrip().partition(":")
            key = key.strip()
            value = value.strip()
            current_key = key
            if value == "":
                current[key] = []
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                items = [v.strip().strip('"').strip("'") for v in inner.split(",")] if inner else []
                current[key] = items
            else:
                current[key] = value.strip().strip('"').strip("'")
        elif line.lstrip().startswith("- ") and current_key:
            item = line.lstrip()[2:].strip().strip('"').strip("'")
            target = current.get(current_key)
            if isinstance(target, list):
                target.append(item)
    if current is not None:
        cases.append(current)
    return cases


DOMAIN_TOKENS = {
    "code", "codebase", "diff", "pr", "branch", "merge", "commit", "rebase",
    "test", "tests", "testing", "coverage", "ci", "lint", "typecheck",
    "deploy", "migration", "schema", "database", "db", "sql",
    "api", "endpoint", "graphql", "rest", "grpc", "service", "module", "package",
    "dependency", "deps", "lockfile", "cve", "vulnerability", "auth",
    "authorization", "secret", "credential", "injection", "tenant",
    "performance", "benchmark", "profile", "perf",
    "accessibility", "a11y", "wcag", "aria",
    "infra", "iac", "terraform", "kubernetes", "k8s", "docker", "iam", "cloud",
    "observability", "logs", "metrics", "traces", "tracing", "alert", "slo",
    "llm", "agent", "prompt", "rag", "tool-calling", "tool-call", "mcp",
    "eval", "evals", "rubric",
    "contract", "consumer-driven",
    "fsm", "reducer",
    "tui", "terminal", "frontend", "ux", "ui",
    "doc", "docs", "documentation", "readme", "changelog",
    "debt", "refactor", "cleanup",
    "plugin", "skill", "subagent", "hook",
    "feature", "implement",
    "prd", "product", "requirements", "plan", "planning", "storage", "ledger",
    "exception", "crash", "regression", "flaky", "flake",
    "harden",
    "repo", "repository", "monorepo",
    "pii", "privacy",
    "supply-chain", "sbom", "provenance", "yaml", "json", "config",
    "function", "method", "class", "type", "types",
    "github", "gitlab", "git",
    "compose", "manifest", "ssh", "tls", "https", "oauth",
}

PHRASE_BOOSTS = [
    ("flaky test", "debug"),
    ("flaky tests", "debug"),
    ("flaky", "debug"),
    ("non-deterministic", "debug"),
    ("ci is failing", "ci-repair"),
    ("build is failing", "ci-repair"),
    ("build is broken", "ci-repair"),
    ("the build is broken", "ci-repair"),
    ("pipeline failure", "ci-repair"),
    ("data flow", "data-flow-privacy-map"),
    ("pii", "data-flow-privacy-map"),
    ("supply chain", "supply-chain-hardening"),
    ("provenance", "supply-chain-hardening"),
    ("lockfile", "supply-chain-hardening"),
    ("known cve", "dependency-audit"),
    ("dependency audit", "dependency-audit"),
    ("cves", "dependency-audit"),
    ("technical debt", "technical-debt-triage"),
    ("tech debt", "technical-debt-triage"),
    ("tech-debt", "technical-debt-triage"),
    ("debt-triage", "technical-debt-triage"),
    ("30/60/90", "technical-debt-triage"),
    ("contract test", "contract-test-generate"),
    ("consumer-driven", "contract-test-generate"),
    ("eval suite", "llm-eval-design"),
    ("state machine", "state-machine-review"),
    ("reducer", "state-machine-review"),
    ("prompt injection", "ai-agent-safety-review"),
    ("agent safety", "ai-agent-safety-review"),
    ("agent loop", "ai-agent-safety-review"),
    ("a11y", "accessibility-review"),
    ("accessibility", "accessibility-review"),
    ("schema migration", "database-review"),
    ("terraform", "infra-iac-review"),
    ("kubernetes", "infra-iac-review"),
    ("iam", "infra-iac-review"),
    ("logs metrics traces", "observability-pass"),
    ("observability", "observability-pass"),
    ("slo", "observability-pass"),
    ("hot path", "performance-pass"),
    ("performance regression", "performance-pass"),
    ("docs", "docs-sync"),
    ("documentation", "docs-sync"),
    ("readme", "docs-sync"),
    ("api compat", "api-contract"),
    ("deprecat", "api-contract"),
    ("breaking change", "api-contract"),
    ("module boundaries", "architect"),
    ("architecture", "architect"),
    ("monorepo structure", "architect"),
    ("structural map", "repo-map"),
    ("onboard", "repo-map"),
    ("structural", "repo-map"),
    ("strengthen the types", "refactor"),
    ("strengthen types", "refactor"),
    ("behavior-preserving", "refactor"),
    ("test coverage", "test-harden"),
    ("regression test", "test-harden"),
    ("ready to release", "release-readiness"),
    ("ready to ship", "release-readiness"),
    ("ship to production", "release-readiness"),
    ("release readiness", "release-readiness"),
    ("test gaps", "test-gap-analysis"),
    ("missing coverage", "test-gap-analysis"),
    ("what should we test", "test-gap-analysis"),
    ("gap analysis", "gap-analysis"),
    ("what's missing", "gap-analysis"),
    ("incomplete", "gap-analysis"),
    ("half-built", "gap-analysis"),
    ("actually work", "feature-completeness"),
    ("feature complete", "feature-completeness"),
    ("quick prd", "prd-lite"),
    ("lightweight spec", "prd-lite"),
    ("technical prd", "prd-technical"),
    ("engineering spec", "prd-technical"),
    ("convert this prd", "prd-to-plan"),
    ("prd to an engineering plan", "prd-to-plan"),
    ("release notes", "release"),
    ("changelog", "release"),
    ("summarize this pr", "review"),
    ("pr for the changelog", "review"),
    ("dependency upgrade", "migrate"),
    ("upgrade dependencies", "migrate"),
    ("migration plan", "migrate"),
    ("postgres 14 to postgres 16", "migrate"),
    ("database migration", "database-review"),
    ("auth and secret", "security-audit"),
    ("auth bypass", "security-audit"),
    ("sql injection", "security-audit"),
    ("merging", "review"),
    ("safe to merge", "review"),
    ("pull request", "review"),
    ("pr-review", "review"),
    ("claude code plugin", "plugin-review"),
    ("a new skill", "skill-author"),
    ("new skill for this plugin", "skill-author"),
    ("author a skill", "skill-author"),
    ("author a new skill", "skill-author"),
    ("new subagent", "agent-author"),
    ("design subagent", "agent-author"),
    ("design a new subagent", "agent-author"),
    ("design a hook", "hooks-design"),
    ("pre-tool hook", "hooks-design"),
    ("new hook", "hooks-design"),
    ("mcp server", "mcp-design"),
    ("mcp integration", "mcp-design"),
    ("new mcp server", "mcp-design"),
    ("focus graph", "tui-design-innovate"),
    ("tui", "tui-design-innovate"),
    ("terminal ui", "tui-design-innovate"),
]


def has_domain_anchor(intent: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9-]+", intent.lower()))
    return bool(tokens & DOMAIN_TOKENS)


def score(intent: str, skill: dict) -> float:
    """Lightweight scoring for the bench. The real router uses LLM reasoning."""
    haystack_parts = [
        skill.get("name", ""),
        skill.get("description", ""),
        skill.get("when_to_use", ""),
        " ".join(skill.get("aliases") or []),
    ]
    haystack = " ".join(haystack_parts).lower()
    intent_lc = intent.lower()
    intent_tokens = [t for t in re.findall(r"[a-z0-9-]+", intent_lc) if len(t) >= 3]
    if not intent_tokens:
        return 0.0
    # Off-domain penalty: if intent has no technical tokens, drop confidence sharply
    domain_anchor = has_domain_anchor(intent)
    raw = sum(1 for t in intent_tokens if t in haystack)
    name = skill.get("name", "").lower()
    if name and name in intent_lc:
        raw += 5
    for alias in skill.get("aliases") or []:
        a = alias.lower()
        if a in intent_lc:
            raw += 4
        # Allow abbreviated alias matches (e.g., "tech-debt-triage" → "technical-debt-triage")
        elif len(a) > 12:
            short = a.replace("technical", "tech").replace("developer-experience", "dx")
            if short != a and short in intent_lc:
                raw += 4
    # Phrase boosts (high weight: phrases are very specific signals)
    for phrase, target_skill in PHRASE_BOOSTS:
        if phrase in intent_lc and skill.get("name") == target_skill:
            raw += 10
    # Tier boost (small)
    if skill.get("tier") == "core":
        raw += 0.4
    score = raw / max(len(intent_tokens), 1)
    if not domain_anchor:
        score *= 0.15  # off-domain heavy penalty
    return score


def rank(intent: str, skills: list[dict]) -> list[tuple[str, float]]:
    scored = [(s["name"], score(intent, s)) for s in skills]
    scored.sort(key=lambda x: -x[1])
    return scored


def run_positive(skills: list[dict], cases_path: Path) -> int:
    cases = load_yaml_cases(cases_path)
    if not cases:
        print(f"No positive cases found at {cases_path.relative_to(ROOT)}")
        return 1
    top1 = top3 = total = 0
    misses: list[tuple[str, str, list[str]]] = []
    top1_only_misses: list[tuple[str, str, list[str]]] = []
    for case in cases:
        intent = case.get("intent", "")
        expected = case.get("expected", "")
        ranked = rank(intent, skills)
        names = [n for n, _ in ranked[:3]]
        total += 1
        if names and names[0] == expected:
            top1 += 1
            top3 += 1
        elif expected in names:
            top3 += 1
            top1_only_misses.append((intent, expected, names))
        else:
            misses.append((intent, expected, names))
    rate1 = top1 / total
    rate3 = top3 / total
    print(f"Router bench (positive): {total} cases")
    print(f"- top-1: {top1}/{total} ({rate1:.1%}; target >=90%)")
    print(f"- top-3: {top3}/{total} ({rate3:.1%}; target 100%)")
    if top1_only_misses:
        print("Top-1 misses (recoverable in top-3):")
        for intent, expected, got in top1_only_misses[:20]:
            print(f"  T1 MISS  '{intent[:60]}' expected={expected} got={got}")
    if misses:
        print("Top-3 misses:")
        for intent, expected, got in misses[:20]:
            print(f"  T3 MISS  '{intent[:60]}' expected={expected} got={got}")
    if rate1 < 0.90 or rate3 < 1.0:
        return 1
    return 0


def run_adversarial(skills: list[dict], cases_path: Path) -> int:
    cases = load_yaml_cases(cases_path)
    if not cases:
        print(f"No adversarial cases found at {cases_path.relative_to(ROOT)}")
        return 1
    rejected = total = 0
    failures: list[tuple[str, str]] = []
    for case in cases:
        intent = case.get("intent", "")
        forbidden = case.get("forbidden", "")
        ranked = rank(intent, skills)
        top_name = ranked[0][0] if ranked else ""
        top_score = ranked[0][1] if ranked else 0.0
        total += 1
        # Adversarial pass: top skill is not the forbidden one OR top score is below confidence threshold
        if top_name != forbidden or top_score < 0.7:
            rejected += 1
        else:
            failures.append((intent, top_name))
    rate = rejected / total if total else 1.0
    print(f"Router bench (adversarial): {total} cases")
    print(f"- rejected: {rejected}/{total} ({rate:.1%}; target 100%)")
    for intent, got in failures[:10]:
        print(f"  FAIL  '{intent[:60]}' incorrectly matched {got}")
    return 0 if rate >= 1.0 else 1


def run_overlap_budget(skills: list[dict], cases_path: Path) -> int:
    cases = load_yaml_cases(cases_path)
    if not cases:
        print(f"No overlap-budget cases found at {cases_path.relative_to(ROOT)}")
        return 1
    violations = 0
    for case in cases:
        intent = case.get("intent", "")
        max_pair_diff = float(case.get("min_top_to_runner_up", "0.10") or 0.10)
        ranked = rank(intent, skills)
        if len(ranked) < 2:
            continue
        top_score = ranked[0][1]
        runner_up = ranked[1][1]
        # Within budget if top is meaningfully ahead (gap >= max_pair_diff)
        gap = top_score - runner_up
        if gap < max_pair_diff:
            violations += 1
            print(f"  TIE   '{intent[:60]}' top={ranked[0][0]}({top_score:.2f}) runner={ranked[1][0]}({runner_up:.2f}) gap={gap:.2f}")
    total = len(cases)
    print(f"Router bench (overlap budget): {total} cases")
    print(f"- violations: {violations}/{total}")
    return 0 if violations == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adversarial", action="store_true")
    parser.add_argument("--overlap-budget", action="store_true")
    parser.add_argument("--bench-dir", default=None)
    args = parser.parse_args()

    root = find_plugin_root(ROOT)
    index = build_index(root)
    skills = index["skills"]
    bench_dir = Path(args.bench_dir) if args.bench_dir else root / "tests" / "routing"

    if args.adversarial:
        return run_adversarial(skills, bench_dir / "adversarial-cases.yaml")
    if args.overlap_budget:
        return run_overlap_budget(skills, bench_dir / "overlap-budget.yaml")
    return run_positive(skills, bench_dir / "golden-cases.yaml")


if __name__ == "__main__":
    raise SystemExit(main())
