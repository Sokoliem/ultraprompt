#!/usr/bin/env python3
"""Shared index and routing utilities for Ultraprompt V8.

Dependency-free so it runs inside Claude Code hooks, CI, and the bundled MCP
server without pip/npm. Provides tier-aware routing, adversarial bench
support, catalog overlap budget computation, and skill spec normalization.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
WORD_RE = re.compile(r"[a-z0-9][a-z0-9+_.-]*", re.I)
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "for", "from",
    "has", "have", "how", "i", "in", "into", "is", "it", "me", "my", "of", "on", "or", "our",
    "that", "the", "this", "to", "use", "using", "want", "we", "when", "with", "without", "you",
    "fix", "review", "check", "make", "need", "help", "please", "run", "create", "update", "change",
}
VALIDATION_COMMAND_PATTERNS = [
    r"\bpytest\b",
    r"\b(npm|pnpm|yarn|bun)\s+(run\s+)?(test|lint|typecheck|check|build)\b",
    r"\bvitest\b",
    r"\bjest\b",
    r"\bgo\s+test\b",
    r"\bcargo\s+(test|check|clippy)\b",
    r"\bruff\b",
    r"\beslint\b",
    r"\btsc\b",
    r"\bmypy\b",
    r"\bpyright\b",
    r"\bphpunit\b",
    r"\bdotnet\s+test\b",
    r"\bmvn\s+test\b",
    r"\bgradle\s+test\b",
    r"\bmake\s+(test|lint|check|build)\b",
    r"\bctest\b",
    r"\bterraform\s+(validate|plan)\b",
    r"\bxcodebuild\s+test\b",
    r"\bswift\s+test\b",
    r"\bbazel\s+test\b",
]

DOMAIN_TOKENS = {
    "agent", "agents", "api", "artifact", "auth", "branch", "bug", "cache",
    "ci", "cli", "code", "codebase", "codex", "component", "config", "contract",
    "database", "db", "dependency", "deploy", "diff", "docs",
    "eval", "feature", "frontend", "git", "github", "hook", "install", "lint",
    "llm", "manifest", "mcp", "memory", "migration", "module", "package",
    "panel", "plugin", "pr", "prd", "privacy", "production", "repo", "routing",
    "schema", "security", "skill", "subagent", "telemetry", "test", "tests",
    "threshold", "thresholds", "tui", "typecheck", "ui", "validation", "version", "workflow",
}

SOURCE_SKILL_METADATA_FIELDS = {
    "editing",
    "mode",
    "risk",
    "confirmation",
    "outputs",
    "output_contract",
    "artifact_type",
    "family",
    "primary_agent",
    "secondary_agents",
    "dispatch_to",
    "preferred_panel",
    "paired_panels",
    "inline_only_reason",
}

# V8 boost rules. Names map to canonical skill names, with legacy aliases handled by alias resolver.
BOOST_RULES: list[tuple[re.Pattern[str], dict[str, float]]] = [
    (re.compile(r"\b(pr|pull request|merge|branch|diff|changed files?|pre[- ]merge)\b", re.I),
     {"review": 28, "release": 4}),
    (re.compile(r"\b(deep review|multi[- ]perspective|cross[- ]cutting|risky migration|panel)\b", re.I),
     {"review": 12, "panel-run": 25}),
    (re.compile(r"\b(repo map|repository map|codebase map|package map|onboarding|where.*start|understand.*repo)\b", re.I),
     {"repo-map": 30}),
    (re.compile(r"\b(find code|where .*handles?|code that handles|signature verification)\b", re.I),
     {"repo-map": 30, "dead-code-drift": -8}),
    (re.compile(r"\b(debug|bug|exception|traceback|stack trace|regression|failing test|crash|broken|flaky|flake|intermittent|non[- ]deterministic|random failure)\b", re.I),
     {"debug": 30, "ci-repair": 6}),
    (re.compile(r"\b(ci|github actions?|workflow|pipeline|build failure|lint failure|typecheck failure|matrix|cache miss)\b", re.I),
     {"ci-repair": 30, "debug": 4}),
    (re.compile(r"\b(build is broken|the build is broken|build failure|fix .*build)\b", re.I),
     {"ci-repair": 34, "build": -8}),
    (re.compile(r"\b(find test gaps?|missing coverage|untested paths?|risk[- ]weighted test plan|what should we test|where'?s the missing coverage|regression coverage review)\b", re.I),
     {"test-gap-analysis": 34, "test-harden": 8}),
    (re.compile(r"(?=.*\b(telemetry|handoffs?|truncat(?:ed|ion)?|cut off|auto[- ]?fir(?:e|ing)|dispatch|pathfinder|routing|explore fallback|live adoption)\b)(?=.*\b(ultraprompt|agents?|skills?|panels?|invocation|routing|pathfinder|plugin)\b)", re.I),
     {"pathfinding-invocation-review": 92, "plugin-review": 8, "observability-pass": -8, "release": -18, "release-readiness": -14}),
    (re.compile(r"\b(design .*validation plan|validation plan .*thresholds?|routing thresholds?|release gates?)\b", re.I),
     {"pathfinding-invocation-review": 30, "test-gap-analysis": 14, "release-readiness": 4}),
    (re.compile(r"\b(release readiness|launch readiness|ship/no-ship|go/no-go|ready to ship|ready to deploy|production-ready|pre[- ]release audit|blocking release|can we deploy)\b", re.I),
     {"release-readiness": 34, "release": 6}),
    (re.compile(r"\b(version ready to release|ready to release|is this version ready)\b", re.I),
     {"release-readiness": 34, "release": -8}),
    (re.compile(r"\b(gap analysis|what'?s missing|incomplete|wiring gaps?|half-built|missing pieces|is feature .* complete|workflow actually work|wired to the backend|persist correctly)\b", re.I),
     {"gap-analysis": 30, "feature-completeness": 18, "repo-review": 6}),
    (re.compile(r"\b(prd for an ai|ai feature prd|llm[- ]based feature spec|agent feature prd|rag feature spec)\b", re.I),
     {"prd-ai-feature": 34, "prd-standard": 4}),
    (re.compile(r"\b(technical prd|engineering spec|infrastructure prd|platform feature spec|technical product doc)\b", re.I),
     {"prd-technical": 34, "prd-standard": 4}),
    (re.compile(r"\b(full prd|standard prd|product requirements doc|comprehensive product spec)\b", re.I),
     {"prd-standard": 32}),
    (re.compile(r"\b(quick prd|lightweight spec|one-pager for feature|opportunity brief|problem-solution memo)\b", re.I),
     {"prd-lite": 32}),
    (re.compile(r"\b(convert this prd|prd to engineering plan|break down prd|make a project plan from this prd)\b", re.I),
     {"prd-to-plan": 34}),
    (re.compile(r"\b(feature|implement|add support|build a|ship)\b", re.I),
     {"build": 26}),
    (re.compile(r"\b(refactor|cleanup|simplify|preserve behavior|behavior-preserving|types?|typing|strict null|generics?)\b", re.I),
     {"refactor": 28}),
    (re.compile(r"\b(test|tests?|coverage|brittle|flaky tests?)\b", re.I),
     {"test-harden": 26, "review": 4}),
    (re.compile(r"\b(security|auth|authorization|secret|credential|injection|xss|csrf|sql injection|tenant isolation)\b", re.I),
     {"security-audit": 32}),
    (re.compile(r"\b(privacy|pii|sensitive data|data flow|retention|deletion|gdpr|ccpa|log redaction)\b", re.I),
     {"data-flow-privacy-map": 30}),
    (re.compile(r"\b(performance|latency|slow|throughput|benchmark|hot path|memory|allocation|scale)\b", re.I),
     {"performance-pass": 30}),
    (re.compile(r"\b(changelog|release notes|release announcement|document this release|what changed in version|publish notes)\b", re.I),
     {"release": 28}),
    (re.compile(r"\b(summarize this pr|pr .*changelog|changelog .*pr)\b", re.I),
     {"review": 34, "release": -10}),
    (re.compile(r"\b(docs?|readme|examples?|comments?|documentation drift|stale)\b", re.I),
     {"docs-sync": 26, "document": 4}),
    (re.compile(r"\b(architecture|boundary|coupling|dependency direction|module design|abstraction|monorepo|workspace)\b", re.I),
     {"architect": 30}),
    (re.compile(r"\b(api|contract|schema|cli|config|event|backward compatibility|breaking change|deprecation|sunset)\b", re.I),
     {"api-contract": 28}),
    (re.compile(r"\b(contract test|contract tests|consumer contract|compatibility test)\b", re.I),
     {"contract-test-generate": 32}),
    (re.compile(r"\b(dependency|dependencies|package audit|lockfile|npm audit|vulnerab)\b", re.I),
     {"dependency-audit": 28}),
    (re.compile(r"\b(supply chain|provenance|sbom|publishing|install script|ci trust)\b", re.I),
     {"supply-chain-hardening": 30}),
    (re.compile(r"\b(upgrade|bump|update dependency|dependency update|migration|migrate|rollout|rollback|backfill|postgres \d+\s+to\s+postgres \d+)\b", re.I),
     {"migrate": 26}),
    (re.compile(r"\b(upgrade dependencies|update dependencies|dependency upgrade)\b", re.I),
     {"migrate": 34, "dependency-audit": -8}),
    (re.compile(r"\b(database|sql|query|index|transaction|schema change|backfill data)\b", re.I),
     {"database-review": 30}),
    (re.compile(r"\b(accessibility|a11y|screen reader|keyboard nav|aria|contrast|wcag)\b", re.I),
     {"accessibility-review": 32}),
    (re.compile(r"\b(design review|taste pass|aesthetic|visual design|product design critique|ui polish|visual polish|make .* feel better|look professional)\b", re.I),
     {"design-review": 34, "frontend-visual-qa": 10}),
    (re.compile(r"\b(visual qa|screenshot qa|responsive qa|frontend polish|browser verify|verify .* ui|pixel check|text clipping|visual overlap|rendered surface)\b", re.I),
     {"frontend-visual-qa": 36, "design-review": 8}),
    (re.compile(r"\b(design system|component library|token audit|theme consistency|ui consistency|component api|design rules)\b", re.I),
     {"design-system-review": 36, "design-review": 8}),
    (re.compile(r"\b(infrastructure|terraform|iac|cloud|kubernetes|helm|aws|gcp|azure|cron|scheduled job|queue|worker)\b", re.I),
     {"infra-iac-review": 28}),
    (re.compile(r"\b(observability|log|logs|trace|metrics|telemetry|alert|slo|dashboard)\b", re.I),
     {"observability-pass": 26}),
    (re.compile(r"\b(state machine|fsm|states?|transitions?|reducer|workflow lifecycle)\b", re.I),
     {"state-machine-review": 32}),
    (re.compile(r"\b(tui|terminal ui|terminal-native|cli ui|ncurses|textual|ratatui|celestial)\b", re.I),
     {"tui-design-innovate": 32}),
    (re.compile(r"\b(eval|evaluation|llm eval|golden case|benchmark prompts?|rubric|grader)\b", re.I),
     {"llm-eval-design": 30}),
    (re.compile(r"\b(ai safety|llm safety|prompt injection|jailbreak|tool calling|agent autonomy|rag trust)\b", re.I),
     {"ai-agent-safety-review": 30}),
    (re.compile(r"\b(claude code plugin|skill author|subagent|agent author|hook|mcp server|claude\.md|slash command)\b", re.I),
     {"plugin-review": 18, "skill-author": 10, "agent-author": 10, "hooks-design": 8, "mcp-design": 8}),
    (re.compile(r"\b(new subagent|design .*subagent|agent author)\b", re.I),
     {"agent-author": 34, "review": -8}),
    (re.compile(r"\b(new mcp server|build .*mcp server|mcp integration)\b", re.I),
     {"mcp-design": 70, "build": -20}),
    (re.compile(r"\b(pathfinding|pathfinder|invocation behavior|skill auto[- ]fire|agent dispatch|routing telemetry|explore fallback|automated invocation|dispatch share)\b", re.I),
     {"pathfinding-invocation-review": 38, "plugin-review": 6}),
    (re.compile(r"\b(automated routing|trigger metrics|skill activation|routing effectiveness|route trigger)\b", re.I),
     {"pathfinding-invocation-review": 38, "observability-pass": -8}),
    (re.compile(r"\b(/goal|set a goal|completion condition|keep working until|do not stop until|work until .* pass|goal mode|codex goal)\b", re.I),
     {"goal": 38}),
    (re.compile(r"\b(technical debt|tech debt|modernization|debt inventory|backlog|onboarding friction|dx|developer experience)\b", re.I),
     {"technical-debt-triage": 28}),
]


def find_plugin_root(start: Path | None = None) -> Path:
    start = (start or Path(__file__).resolve()).resolve()
    candidates = [start] if start.is_dir() else [start.parent]
    candidates += list(candidates[0].parents)
    for candidate in candidates:
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    return Path(__file__).resolve().parents[1]


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path}: missing closing frontmatter delimiter")
    raw = text[4:end]
    body = text[end + 5:]
    data: dict[str, str] = {}
    key: str | None = None
    values: list[str] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            if key is not None:
                data[key] = "\n".join(values).strip()
            key, value = line.split(":", 1)
            values = [value.strip()]
            key = key.strip()
        elif key is not None:
            values.append(line)
        else:
            raise ValueError(f"{path}: malformed frontmatter line: {line!r}")
    if key is not None:
        data[key] = "\n".join(values).strip()
    return data, body


def clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    return text.strip()


def truthy(value: Any) -> bool:
    return clean_scalar(value).lower() == "true"


def load_source_skill_metadata(root: Path) -> dict[str, dict[str, Any]]:
    """Return cognitive routing metadata from canonical source specs.

    Generated SKILL.md frontmatter is intentionally small, but runtime routing,
    pathfinding, and dashboard details need the richer source-of-truth metadata.
    """
    path = root / "source" / "skill-specs.json"
    if not path.exists():
        return {}
    try:
        specs = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    metadata: dict[str, dict[str, Any]] = {}
    for spec in specs:
        name = str(spec.get("name", ""))
        if not name:
            continue
        entry: dict[str, Any] = {}
        cognitive = spec.get("cognitive") or {}
        for field in SOURCE_SKILL_METADATA_FIELDS:
            if field in spec:
                entry[field] = spec[field]
            elif isinstance(cognitive, dict) and field in cognitive:
                entry[field] = cognitive[field]
        metadata[name] = entry
    return metadata


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for raw in WORD_RE.findall(text.lower()):
        parts = re.split(r"[-_/.:]+", raw)
        for part in parts:
            if len(part) >= 2 and part not in STOPWORDS:
                tokens.append(part)
    lowered = text.lower()
    phrases = {
        "pull request": "pullrequest",
        "github actions": "githubactions",
        "feature flag": "featureflag",
        "state machine": "statemachine",
        "supply chain": "supplychain",
        "data flow": "dataflow",
        "design doc": "designdoc",
        "tech debt": "techdebt",
    }
    for phrase, token in phrases.items():
        if phrase in lowered:
            tokens.append(token)
    return tokens


def build_index(root: Path) -> dict[str, Any]:
    skills: list[dict[str, Any]] = []
    agents: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    aliases: dict[str, str] = {}
    source_skill_metadata = load_source_skill_metadata(root)

    skills_root = root / "skills"
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_path = skill_dir / "SKILL.md"
            if not skill_path.exists():
                continue
            front, body = parse_frontmatter(skill_path)
            name = clean_scalar(front.get("name") or skill_dir.name)
            description = clean_scalar(front.get("description"))
            when_to_use = clean_scalar(front.get("when_to_use"))
            tier = clean_scalar(front.get("tier") or "core")
            paths = clean_scalar(front.get("paths"))
            manual_only = truthy(front.get("disable-model-invocation"))
            alias_field = clean_scalar(front.get("aliases"))
            # Aliases may be a YAML list ["a", "b", "c"] or comma-separated; handle both.
            if alias_field.startswith("[") and alias_field.endswith("]"):
                inner = alias_field[1:-1].strip()
                entry_aliases = [a.strip().strip('"').strip("'") for a in inner.split(",") if a.strip()]
            else:
                entry_aliases = [a.strip().strip('"').strip("'") for a in alias_field.split(",") if a.strip()] if alias_field else []
            for alias in entry_aliases:
                aliases[alias] = name
            tokens = sorted(set(tokenize(f"{name} {description} {when_to_use}")))
            entry = {
                "name": name,
                "command": f"/ultraprompt:{name}",
                "codex_command": f"$ultraprompt:{name}",
                "description": description,
                "when_to_use": when_to_use,
                "tier": tier,
                "paths": paths,
                "manual_only": manual_only,
                "tokens": tokens,
                "aliases": entry_aliases,
                "path": str(skill_path.relative_to(root)),
            }
            entry.update(source_skill_metadata.get(name, {}))
            skills.append(entry)

    agents_root = root / "agents"
    if agents_root.is_dir():
        for agent_path in sorted(agents_root.glob("*.md")):
            front, _body = parse_frontmatter(agent_path)
            name = clean_scalar(front.get("name") or agent_path.stem)
            agents.append({
                "name": name,
                "description": clean_scalar(front.get("description")),
                "tools": clean_scalar(front.get("tools")),
                "disallowed_tools": clean_scalar(front.get("disallowedTools")),
                "max_turns": clean_scalar(front.get("maxTurns")),
                "color": clean_scalar(front.get("color")),
                "path": str(agent_path.relative_to(root)),
            })

    commands_root = root / "commands"
    if commands_root.is_dir():
        for cmd_path in sorted(commands_root.glob("*.md")):
            front, _body = parse_frontmatter(cmd_path)
            commands.append({
                "name": cmd_path.stem,
                "description": clean_scalar(front.get("description")),
                "manual_only": truthy(front.get("disable-model-invocation")),
                "path": str(cmd_path.relative_to(root)),
            })

    manifest_path = root / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "plugin": {
            "name": manifest.get("name", "ultraprompt"),
            "version": manifest.get("version", "0.0.0"),
            "description": manifest.get("description", ""),
        },
        "counts": {"skills": len(skills), "agents": len(agents), "commands": len(commands)},
        "skills": skills,
        "agents": agents,
        "commands": commands,
        "aliases": aliases,
    }


def write_index(root: Path | None = None, *, check: bool = False) -> Path:
    root = find_plugin_root(root)
    index = build_index(root)
    target = root / "dist" / "skill-index.json"
    rendered = json.dumps(index, indent=2, sort_keys=True) + "\n"
    if check:
        if not target.exists():
            raise SystemExit("dist/skill-index.json is missing; run scripts/build-skill-index.py")
        existing_json = json.loads(target.read_text(encoding="utf-8"))
        existing_json["generated_at"] = index["generated_at"]
        existing_normalized = json.dumps(existing_json, indent=2, sort_keys=True) + "\n"
        if existing_normalized != rendered:
            raise SystemExit("dist/skill-index.json is stale; run scripts/build-skill-index.py")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8")
    return target


def load_index(root: Path | None = None) -> dict[str, Any]:
    root = find_plugin_root(root)
    target = root / "dist" / "skill-index.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    return build_index(root)


def resolve_alias(index: dict[str, Any], name: str) -> tuple[str, bool]:
    """Return (canonical_name, is_aliased)."""
    needle = name.strip().removeprefix("/ultraprompt:").removeprefix("$ultraprompt:")
    aliases = index.get("aliases") or {}
    if needle in aliases:
        return aliases[needle], True
    return needle, False


def score_skill(skill: dict[str, Any], intent: str) -> float:
    intent_tokens = tokenize(intent)
    if not intent_tokens:
        return 0.0
    intent_set = set(intent_tokens)
    skill_tokens = set(skill.get("tokens") or [])
    desc_tokens = set(tokenize(str(skill.get("description", ""))))
    when_tokens = set(tokenize(str(skill.get("when_to_use", ""))))
    name_tokens = set(tokenize(str(skill.get("name", "").replace("-", " "))))

    score = 0.0
    score += 3.0 * len(intent_set & skill_tokens)
    score += 3.5 * len(intent_set & desc_tokens)
    score += 4.0 * len(intent_set & when_tokens)
    score += 8.0 * len(intent_set & name_tokens)

    lowered = intent.lower()
    name = str(skill.get("name"))
    explicit_command = re.search(
        rf"(?<![a-z0-9-])(?:\$ultraprompt:|/ultraprompt:|ultraprompt:){re.escape(name)}(?![a-z0-9-])",
        lowered,
    )
    if explicit_command:
        score += 120.0
    if name in lowered or name.replace("-", " ") in lowered:
        score += 35.0
    for pattern, boosts in BOOST_RULES:
        if pattern.search(intent):
            score += boosts.get(name, 0.0)

    paths = str(skill.get("paths", ""))
    if paths and any(fragment and fragment in lowered for fragment in re.split(r"[\s,]+", paths.lower())):
        score += 5.0

    # Tier preferences: prefer core unless the intent is ecosystem-flavored.
    tier = str(skill.get("tier", "core"))
    if tier == "specialist":
        score -= 1.0
    elif tier == "ecosystem":
        score -= 1.5
    if skill.get("manual_only"):
        score -= 0.5
    if len(skill_tokens) > 45:
        score -= math.log(len(skill_tokens) - 44)
    if not explicit_command and not (set(intent_tokens) & DOMAIN_TOKENS):
        score *= 0.05
    return round(score, 3)


def confidence_from_score(score: float, best: float) -> str:
    if score >= 28 or (best and score >= best * 0.85 and score >= 18):
        return "high"
    if score >= 12 or (best and score >= best * 0.55 and score >= 8):
        return "medium"
    return "low"


def route_intent(index: dict[str, Any], intent: str, limit: int = 3) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any]]] = []
    for skill in index.get("skills", []):
        score = score_skill(skill, intent)
        if score > 0:
            scored.append((score, skill))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("name", ""))))
    if not scored:
        return []
    best = scored[0][0]
    results: list[dict[str, Any]] = []
    for score, skill in scored[: max(1, limit)]:
        name = skill.get("name", "")
        results.append({
            "skill": name,
            "command": skill.get("command") or f"/ultraprompt:{name}",
            "codex_command": skill.get("codex_command") or f"$ultraprompt:{name}",
            "confidence": confidence_from_score(score, best),
            "score": score,
            "tier": skill.get("tier", "core"),
            "why": make_route_reason(skill, intent),
            "manual_only": bool(skill.get("manual_only")),
            "path": skill.get("path", ""),
        })
    return results


def make_route_reason(skill: dict[str, Any], intent: str) -> str:
    desc = str(skill.get("description") or "").rstrip(".")
    if not desc:
        desc = f"Matches the requested {skill.get('name')} workflow"
    intent_terms = sorted(set(tokenize(intent)) & set(skill.get("tokens") or []))
    if intent_terms[:3]:
        return f"{desc}; matched: {', '.join(intent_terms[:3])}."
    return f"{desc}."


def explain_skill(index: dict[str, Any], name: str) -> dict[str, Any] | None:
    canonical, _aliased = resolve_alias(index, name)
    for skill in index.get("skills", []):
        if skill.get("name") == canonical:
            return skill
    return None


def compose_workflow(index: dict[str, Any], skills: list[str]) -> dict[str, Any]:
    """Deprecated; use team_plan for orchestration. Kept for backward compat."""
    steps: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in skills:
        skill = explain_skill(index, item)
        if not skill:
            missing.append(item)
            continue
        steps.append({
            "skill": skill["name"],
            "invoke": skill["command"],
            "codex_invoke": skill.get("codex_command") or f"$ultraprompt:{skill['name']}",
            "purpose": skill.get("description", ""),
            "handoff": "Capture changed files, commands run, evidence, risks, and next validation before moving to the next step.",
        })
    return {
        "steps": steps,
        "missing": missing,
        "deprecated": True,
        "note": "compose_workflow is deprecated. Use team_plan for parallelizable orchestration.",
    }


def is_validation_command(command: str) -> bool:
    return any(re.search(pattern, command, flags=re.I) for pattern in VALIDATION_COMMAND_PATTERNS)


def validate_plugin(root: Path | None = None) -> dict[str, Any]:
    root = find_plugin_root(root)
    cmd = [sys.executable, str(root / "scripts" / "validate-plugin.py")]
    completed = subprocess.run(cmd, cwd=str(root), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    return {"returncode": completed.returncode, "output": completed.stdout[-8000:]}


def overlap_budget_check(index: dict[str, Any], cases: list[dict[str, Any]], threshold: float = 0.10) -> list[dict[str, Any]]:
    """For each case, if the top two skills score within `threshold` of each other (relative to top score),
    flag as overlap. Returns list of violations."""
    violations: list[dict[str, Any]] = []
    for case in cases:
        intent = case.get("intent", "")
        routes = route_intent(index, intent, limit=5)
        if len(routes) < 2:
            continue
        top, second = routes[0], routes[1]
        if top["score"] <= 0:
            continue
        gap = (top["score"] - second["score"]) / top["score"]
        if gap < threshold:
            violations.append({
                "id": case.get("id"),
                "intent": intent,
                "top": top["skill"],
                "second": second["skill"],
                "top_score": top["score"],
                "second_score": second["score"],
                "gap_pct": round(gap * 100, 2),
            })
    return violations
