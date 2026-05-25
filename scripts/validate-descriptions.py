#!/usr/bin/env python3
"""Validate skill, agent, and command descriptions against V8.8 lint rules.

Lint rules (per PRD-V8.8 §7.3):
  MALFORMED_PARENS         description has unbalanced parens
  TRUNCATED_SENTENCE       core/specialist description ends with the sparse fallback
  SELF_ALIAS               aliases list contains the entity's own name
  MISSING_DIFFERENT_FROM   tier=core description lacks "Different from" disambiguation
  TOOL_DISALLOWED_COLLISION  agent has the same token in tools and disallowedTools
  STATIC_COUNT_IN_MANAGED_FILE  managed file has hand-typed "N skills/agents/..." token
  MOJIBAKE                 double-encoded UTF-8 sequence in any tracked text file
  MISSING_DISPATCH_POLICY  tier=core skill body lacks Dispatch policy (V8) section
  KEYWORD_BLOAT            plugin.json keywords list exceeds 10 entries

Exit codes:
  0 — no errors (warnings may be present)
  1 — at least one error finding
  2 — script failure (e.g., unreadable file)

CLI:
  --strict             treat warnings as errors
  --json               emit JSON findings to stdout instead of text
  --check              shorthand for default error gating
  --files <glob...>    limit lint to specified globs (default: all managed files)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _ledger_write(event_type: str, **fields) -> None:
    """Emit a ledger v2 event. Fail-open."""
    if os.environ.get("ULTRAPROMPT_DISABLE_TELEMETRY") == "1":
        return
    try:
        spec = importlib.util.spec_from_file_location("led", ROOT / "scripts" / "ledger-v2.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.write_event(event_type, **fields)
    except Exception:
        pass
SKILL_SPECS = ROOT / "source" / "skill-specs.json"
AGENT_SPECS = ROOT / "source" / "agent-specs.json"
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"
MANAGED_COUNT_FILES = [
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".claude-plugin" / "marketplace.json",
    ROOT / "commands" / "menu.md",
    ROOT / "commands" / "dashboard.md",
]

# Mojibake byte patterns (cp1252-rendered UTF-8): match the decoded string form
MOJIBAKE_PATTERNS = ["â€”", "â€“", "â‰¤", "Ã—", "â†’", "â€œ", "â€\x9d"]

# Static-count regex: "<num> <noun>" with skills/agents/MCP tools/commands
STATIC_COUNT_RE = re.compile(
    r"\b(\d{2,3})\s+(skills?|agents?|MCP tools?|commands?|hooks?|panels?|artifact schemas?|output styles?)\b",
    re.IGNORECASE,
)

# Truncated-sentence canary: V7-era fallback templates we're stamping out
TRUNCATED_RE = re.compile(r":\s*runs the [a-z0-9_-]+ discipline\.\*\*$", re.IGNORECASE)


def add(findings: list, rule: str, severity: str, file: str, line: int, message: str,
        suggested_fix: str | None = None) -> None:
    findings.append({
        "rule": rule,
        "severity": severity,
        "file": file,
        "line": line,
        "message": message,
        "suggested_fix": suggested_fix,
    })


def lint_skill(spec: dict, findings: list) -> None:
    name = spec.get("name", "<unknown>")
    desc = spec.get("description", "") or ""
    aliases = spec.get("aliases") or []
    tier = spec.get("tier", "specialist")
    rel = f"skills/{name}/SKILL.md"

    if desc.count("(") != desc.count(")"):
        add(findings, "MALFORMED_PARENS", "error", rel, 3,
            f"Description has unbalanced parens (open={desc.count('(')}, close={desc.count(')')})",
            suggested_fix="Balance parens or remove the offending opener/closer.")

    if tier in {"core", "specialist"} and TRUNCATED_RE.search(desc):
        add(findings, "TRUNCATED_SENTENCE", "error", rel, 3,
            "Description matches the sparse fallback template ': runs the X discipline.**'",
            suggested_fix="Rewrite as: '**DEFAULT for <X> — <produces Y>.** Different from <peer> (<why>). Triggers: '<phrases>'.")

    if name in aliases:
        add(findings, "SELF_ALIAS", "error", rel, 7,
            f"Skill '{name}' is listed as its own alias.",
            suggested_fix=f"Remove '{name}' from the aliases list.")

    if tier == "core" and "Different from" not in desc:
        add(findings, "MISSING_DIFFERENT_FROM", "error", rel, 3,
            "tier=core skill description lacks 'Different from' disambiguation clause.",
            suggested_fix="Add 'Different from /<peer> (<why>), /<peer> (<why>).' clause.")


def lint_agent(spec: dict, findings: list) -> None:
    name = spec.get("name", "<unknown>")
    tools = {t.strip() for t in (spec.get("tools") or "").split(",") if t.strip()}
    disallowed = {t.strip() for t in (spec.get("disallowed_tools") or "").split(",") if t.strip()}
    rel = f"agents/{name}.md"

    collisions = tools & disallowed
    if collisions:
        add(findings, "TOOL_DISALLOWED_COLLISION", "error", rel, 6,
            f"Agent '{name}' has tokens in both tools and disallowed_tools: {sorted(collisions)}",
            suggested_fix=f"Remove {sorted(collisions)} from either tools or disallowed_tools.")


def lint_managed_count_file(path: Path, findings: list) -> None:
    if not path.exists():
        return
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    # V8.8 S2: skip if a .tmpl sibling exists — file is rendered from template.
    tmpl_path = path.with_suffix(path.suffix + ".tmpl")
    if tmpl_path.exists():
        return
    text = path.read_text(encoding="utf-8")
    for idx, line in enumerate(text.splitlines(), 1):
        m = STATIC_COUNT_RE.search(line)
        if m:
            add(findings, "STATIC_COUNT_IN_MANAGED_FILE", "warn", rel, idx,
                f"Hand-typed count '{m.group(0)}' in {rel}: prefer template token (V8.8 S2).",
                suggested_fix="Replace with templating token rendered from dist/catalog-metadata.json.")


def lint_mojibake(findings: list) -> None:
    # Scan a small set of high-value tracked files for mojibake.
    candidates = (
        list(ROOT.glob("mcp/*.py"))
        + list(ROOT.glob("scripts/*.py"))
        + list(ROOT.glob("commands/*.md"))
        + list(ROOT.glob("skills/*/SKILL.md"))
        + list(ROOT.glob("agents/*.md"))
        + list(ROOT.glob(".claude-plugin/*.json"))
    )
    self_path = Path(__file__).resolve()
    for path in candidates:
        # Skip self — the validator must contain mojibake patterns as literals to detect them.
        if path.resolve() == self_path:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for needle in MOJIBAKE_PATTERNS:
            if needle in text:
                line = text[: text.index(needle)].count("\n") + 1
                rel = str(path.relative_to(ROOT)).replace("\\", "/")
                add(findings, "MOJIBAKE", "error", rel, line,
                    f"Mojibake sequence {needle!r} detected — file likely double-encoded.",
                    suggested_fix="Re-encode with UTF-8; replace mojibake byte sequences with the intended characters.")
                break  # one finding per file


def lint_keywords(findings: list) -> None:
    if not PLUGIN_JSON.exists():
        return
    try:
        data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    keywords = data.get("keywords") or []
    if len(keywords) > 10:
        add(findings, "KEYWORD_BLOAT", "warn", ".claude-plugin/plugin.json", 1,
            f"plugin.json keywords list has {len(keywords)} entries (>10); prune to 6-8 for discovery quality.",
            suggested_fix="Keep claude-code, codex, mcp-server, hooks, agentic-ai, code-review, security, observability.")


def lint_self_ranking(findings: list) -> None:
    """V8.9 (PQ3 CI gate): for each tier=core or tier=specialist skill, verify the skill's own
    `description_meta.triggers` phrases route to it as top-1 or top-2 via the V8 router.

    A weak self-ranking ⇒ the description copy doesn't match the trigger phrases it claims to
    handle — exactly what a prompt-engineer review should catch. We implement it as a lint rule
    so CI catches drift without requiring an LLM in the CI loop.
    """
    if not SKILL_SPECS.exists():
        return
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from ultraprompt_index import build_index, find_plugin_root, route_intent  # type: ignore
    except Exception:
        return  # If the router module is unavailable, skip silently.
    try:
        root = find_plugin_root(ROOT)
        index = build_index(root)
    except Exception:
        return

    specs = json.loads(SKILL_SPECS.read_text(encoding="utf-8"))
    for spec in specs:
        tier = spec.get("tier")
        if tier not in {"core", "specialist"}:
            continue
        name = spec["name"]
        meta = spec.get("description_meta") or {}
        triggers_raw = (meta.get("triggers") or "").strip()
        if not triggers_raw:
            continue
        # Split on comma, semicolon, ' / ', or " — "; ignore very short phrases.
        candidates = [p.strip().strip("'\"") for p in re.split(r"[;,]| / | — ", triggers_raw) if p.strip()]
        # Filter: at least 3 words; skip phrases with <placeholder> tokens or
        # single-cap-letter placeholders (X, Y, Z, A, B) — those are doc templates,
        # not literal routing triggers.
        single_cap = re.compile(r"\b[A-Z]\b")
        candidates = [c for c in candidates
                      if len(c.split()) >= 3 and "<" not in c and not single_cap.search(c)]
        if not candidates:
            continue
        sample = candidates[:3]  # cap so the lint stays under ~150ms for 55 skills
        for phrase in sample:
            try:
                routed = route_intent(index, phrase, limit=3)
            except Exception:
                break
            if not routed:
                continue
            ranks = {r.get("skill"): i for i, r in enumerate(routed)}
            if ranks.get(name, 99) >= 2:  # not in top-2
                rel = f"skills/{name}/SKILL.md"
                top = routed[0].get("skill")
                add(findings, "WEAK_SELF_RANKING", "warn", rel, 3,
                    f"Skill '{name}' trigger phrase {phrase!r} ranks outside top-2 "
                    f"(top-1='{top}'). Tighten description to match its declared triggers.",
                    suggested_fix="Use `prompt-engineer` agent to rewrite the description for routing precision.")
                break  # one finding per skill is enough


def lint_dispatch_policy(findings: list) -> None:
    # tier=core skills should reference Dispatch policy (V8), UNLESS they are
    # documented inline-only / non-dispatching skills.
    if not SKILL_SPECS.exists():
        return
    inline_only = {"refactor", "migrate", "choose", "llm-eval-design",
                   "tui-design-innovate", "contract-test-generate"}
    specs = json.loads(SKILL_SPECS.read_text(encoding="utf-8"))
    skill_dir = ROOT / "skills"
    for spec in specs:
        if spec.get("tier") != "core":
            continue
        name = spec["name"]
        if name in inline_only:
            continue
        skill_md = skill_dir / name / "SKILL.md"
        if not skill_md.exists():
            continue
        body = skill_md.read_text(encoding="utf-8")
        if "Dispatch policy (V8)" not in body:
            rel = f"skills/{name}/SKILL.md"
            add(findings, "MISSING_DISPATCH_POLICY", "warn", rel, 1,
                f"tier=core skill '{name}' lacks 'Dispatch policy (V8)' section in body.",
                suggested_fix="Add a Dispatch policy (V8) heading referencing _shared/DISPATCH-POLICY.md.")


def lint_mcp_risk_annotations(findings: list) -> None:
    """V9.0 R6: every registered MCP tool must declare all 4 MCP-spec annotation keys."""
    required = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
    try:
        import importlib.util as _iu
        spec = _iu.spec_from_file_location("_um", ROOT / "mcp" / "ultraprompt_meta.py")
        if not spec or not spec.loader:
            return
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception:
        return  # MCP module unavailable; skip silently
    tools = getattr(mod, "TOOLS", {})
    for name, entry in tools.items():
        annotations = entry[3] if len(entry) > 3 else {}
        missing = required - set(annotations.keys())
        if missing:
            add(findings, "MCP_RISK_HINTS_MISSING", "warn",
                "mcp/ultraprompt_meta.py", 1,
                f"MCP tool '{name}' missing annotation keys: {sorted(missing)}",
                suggested_fix="Add destructiveHint/idempotentHint/openWorldHint per MCP spec.")


def run_lint() -> list[dict]:
    findings: list[dict] = []
    if SKILL_SPECS.exists():
        for spec in json.loads(SKILL_SPECS.read_text(encoding="utf-8")):
            lint_skill(spec, findings)
    if AGENT_SPECS.exists():
        for spec in json.loads(AGENT_SPECS.read_text(encoding="utf-8")):
            lint_agent(spec, findings)
    for f in MANAGED_COUNT_FILES:
        lint_managed_count_file(f, findings)
    lint_mojibake(findings)
    lint_keywords(findings)
    lint_dispatch_policy(findings)
    lint_self_ranking(findings)
    lint_mcp_risk_annotations(findings)

    # Telemetry: per PRD §10.2, emit one description-lint-finding event per finding.
    pr_ref = os.environ.get("GITHUB_REF") or os.environ.get("PR_REF")
    for f in findings:
        _ledger_write(
            "description-lint-finding",
            rule=f["rule"],
            file=f["file"],
            line=f["line"],
            severity=f["severity"],
            pr_ref=pr_ref,
        )
    # Per-agent policy validation summary (PRD §10.2 agent-tool-policy-validated)
    if AGENT_SPECS.exists():
        for spec in json.loads(AGENT_SPECS.read_text(encoding="utf-8")):
            tools = {t.strip() for t in (spec.get("tools") or "").split(",") if t.strip()}
            disallowed = {t.strip() for t in (spec.get("disallowed_tools") or "").split(",") if t.strip()}
            collisions = sorted(tools & disallowed)
            _ledger_write(
                "agent-tool-policy-validated",
                agent=spec.get("name"),
                tools_count=len(tools),
                disallowed_count=len(disallowed),
                collisions=collisions,
                bash_allowlist_present=bool(spec.get("bash_guard")),
            )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="V8.8 description lint")
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument("--json", action="store_true", help="emit JSON findings")
    parser.add_argument("--check", action="store_true", help="default error gating")
    args = parser.parse_args()

    findings = run_lint()
    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warn"]

    if args.json:
        out = {
            "ok": not errors and (not warnings if args.strict else True),
            "findings": findings,
            "summary": {
                "errors": len(errors),
                "warnings": len(warnings),
                "total": len(findings),
            },
        }
        print(json.dumps(out, indent=2))
    else:
        for f in findings:
            print(f"[{f['severity'].upper():5}] {f['rule']:30} {f['file']}:{f['line']}  {f['message']}")
            if f["suggested_fix"]:
                print(f"        FIX: {f['suggested_fix']}")
        print(f"\nSummary: {len(errors)} errors, {len(warnings)} warnings, {len(findings)} total")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
