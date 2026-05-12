#!/usr/bin/env python3
"""V8.2.0: Release scorecard.

Generates a release-readiness scorecard for the plugin itself. Covers manifest,
discovery, routing, safety, docs, install dimensions.

Outputs YAML for downstream consumption + human-readable summary.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CODEX_CACHE = Path.home() / ".codex" / "plugins" / "cache" / "local-marketplace" / "ultraprompt"
CLAUDE_INSTALLED_PLUGINS = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
CLAUDE_PLUGIN_ID = "ultraprompt@local-marketplace"
CLAUDE_INSTALL_CANDIDATES = [
    Path.home() / ".claude" / "plugins" / "marketplaces" / "local-marketplace" / "ultraprompt",
    Path.home() / ".claude" / "plugins" / "marketplaces" / "local-marketplace" / "ultra-prompt",
]


def run(cmd, *, cwd: Path | None = None, timeout: int = 120):
    try:
        out = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True, timeout=timeout)
        return out.returncode, out.stdout, out.stderr
    except Exception as e:
        return -1, "", str(e)


def plugin_version() -> str:
    for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        try:
            data = json.load(open(ROOT / rel))
            version = data.get("version")
            if version:
                return str(version)
        except Exception:
            continue
    return "unknown"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def git_value(args: list[str]) -> str | None:
    code, out, _ = run(["git", *args], timeout=10)
    if code == 0:
        return out.strip() or None
    return None


def dirty_state() -> str:
    code, out, _ = run(["git", "status", "--porcelain"], timeout=10)
    if code != 0:
        return "unknown"
    return "dirty" if out.strip() else "clean"


def semver_key(path: Path) -> tuple[int, ...]:
    parts = []
    for part in path.name.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def count_mcp_tools(root: Path) -> int | None:
    mcp_path = root / "mcp" / "ultraprompt_meta.py"
    if not mcp_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("ultraprompt_meta_for_scorecard", mcp_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tools = getattr(module, "TOOLS", None)
        return len(tools) if isinstance(tools, dict) else None
    except Exception:
        return None


def catalog_counts(root: Path) -> dict[str, int | None]:
    return {
        "skill_count": sum(1 for p in (root / "skills").iterdir() if p.is_dir()) if (root / "skills").exists() else None,
        "agent_count": sum(1 for p in (root / "agents").glob("*.md")) if (root / "agents").exists() else None,
        "command_count": sum(1 for p in (root / "commands").glob("*.md")) if (root / "commands").exists() else None,
        "mcp_tool_count": count_mcp_tools(root),
    }


def manifest_path(root: Path, runtime: str) -> Path:
    if runtime == "codex":
        return root / ".codex-plugin" / "plugin.json"
    if runtime == "claude-code":
        return root / ".claude-plugin" / "plugin.json"
    return root / ".claude-plugin" / "plugin.json"


def runtime_target_status(
    name: str,
    root: Path,
    *,
    runtime: str,
    expected: dict[str, Any],
    next_action: str | None = None,
    checks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    manifest = manifest_path(root, runtime)
    data = load_json(manifest)
    counts = catalog_counts(root) if root.exists() else {
        "skill_count": None,
        "agent_count": None,
        "command_count": None,
        "mcp_tool_count": None,
    }
    if not root.exists():
        findings.append("runtime target path missing")
    if not manifest.exists():
        findings.append(f"{runtime} manifest missing")
    version = str(data.get("version") or "missing")
    if version != expected.get("version"):
        findings.append(f"version {version} != source {expected.get('version')}")
    for field in ("skill_count", "agent_count", "command_count"):
        actual = counts.get(field)
        want = expected.get(field)
        if actual is None:
            findings.append(f"{field} unavailable")
        elif want is not None and actual != want:
            findings.append(f"{field} {actual} != source {want}")
    actual_mcp = counts.get("mcp_tool_count")
    expected_mcp = expected.get("mcp_tool_count")
    if actual_mcp is not None and expected_mcp is not None and actual_mcp != expected_mcp:
        findings.append(f"mcp_tool_count {actual_mcp} != source {expected_mcp}")
    return {
        "target": name,
        "path": str(root),
        "runtime": runtime,
        "version": version,
        **counts,
        "ok": not findings and bool(root.exists()),
        "findings": findings,
        "next_action": next_action,
        "checks": checks or {},
    }


def source_expected() -> dict[str, Any]:
    return {"version": plugin_version(), **catalog_counts(ROOT)}


def resolve_manifest_ref(ref: str) -> Path:
    rel = ref[2:] if ref.startswith("./") else ref
    return ROOT / rel


def manifest_status(path: Path) -> dict:
    data = load_json(path)
    missing_fields = [field for field in ("name", "version", "description") if field not in data]
    missing_refs = []
    invalid_refs = []
    for field in ("mcpServers", "hooks", "outputStyles"):
        ref = data.get(field)
        if isinstance(ref, str):
            if (
                field == "hooks"
                and ref.removeprefix("./") == "hooks/hooks.json"
                and ".claude-plugin" in path.parts
            ):
                invalid_refs.append({
                    "field": field,
                    "path": ref,
                    "reason": "Claude Code auto-loads hooks/hooks.json; manifest reference is duplicate",
                })
            if not resolve_manifest_ref(ref).exists():
                missing_refs.append({"field": field, "path": ref})
    return {
        "path": str(path.relative_to(ROOT)),
        "valid": path.exists() and not missing_fields and not missing_refs and not invalid_refs,
        "present": path.exists(),
        "missing_fields": missing_fields,
        "missing_references": missing_refs,
        "invalid_references": invalid_refs,
    }


def check_manifests():
    claude = manifest_status(ROOT / ".claude-plugin/plugin.json")
    codex = manifest_status(ROOT / ".codex-plugin/plugin.json")
    return {
        "claude_valid": claude["valid"],
        "codex_valid": codex["valid"],
        "claude": claude,
        "codex": codex,
    }


def check_discovery():
    skills = sum(1 for p in (ROOT / "skills").iterdir() if p.is_dir())
    agents = sum(1 for p in (ROOT / "agents").glob("*.md"))
    commands = sum(1 for p in (ROOT / "commands").glob("*.md"))
    return {
        "skills_discovered": skills,
        "agents_discovered": agents,
        "commands_discovered": commands,
    }


def check_routing():
    code, out, _ = run([sys.executable, str(ROOT / "scripts/run-router-bench.py")])
    top1 = top3 = None
    for line in out.splitlines():
        if "top-1:" in line:
            try: top1 = float(line.split("(")[1].split("%")[0])
            except: pass
        if "top-3:" in line:
            try: top3 = float(line.split("(")[1].split("%")[0])
            except: pass
    return {"top1_accuracy": top1, "top3_accuracy": top3}


def check_safety():
    code, out, _ = run([sys.executable, str(ROOT / "scripts/run-hook-tests.py")])
    hook_passed = "passed: 26" in out or "failed: 0" in out
    coverage_code, coverage_out, _ = run([sys.executable, str(ROOT / "scripts/audit-hook-coverage.py"), "--json"])
    try:
        coverage = json.loads(coverage_out)
    except Exception:
        coverage = {"ok": False, "error": coverage_out.strip(), "exit": coverage_code}
    return {"hook_fixtures": "pass" if hook_passed else "fail", "hook_coverage": coverage}


def check_docs():
    code, out, _ = run([sys.executable, str(ROOT / "scripts/audit-doc-metadata.py")])
    try:
        stale_count = len(json.loads(out).get("findings", []))
    except Exception:
        stale_count = 1
    return {"stale_version_refs": stale_count, "audit_exit": code}


def check_trust_gates():
    gates = {
        "plugin_validation": run([sys.executable, str(ROOT / "scripts/validate-plugin.py"), "--target-runtime", "source", "--strict-runtime-files"]),
        "manifest_schema_claude": run([sys.executable, str(ROOT / "scripts/audit-manifest-schemas.py"), "--runtime", "claude-code", "--strict-references"]),
        "manifest_schema_codex": run([sys.executable, str(ROOT / "scripts/audit-manifest-schemas.py"), "--runtime", "codex", "--strict-references"]),
        "catalog_consistency": run([sys.executable, str(ROOT / "scripts/audit-catalog-consistency.py"), "--json"]),
        "package_verify": run([sys.executable, str(ROOT / "scripts/package-plugin.py"), "--verify-only"]),
        "install_simulation": run([sys.executable, str(ROOT / "scripts/install-simulate.py"), "--runtime", "both"]),
        "config_env_overrides": run([sys.executable, str(ROOT / "scripts/run-config-tests.py")]),
        "artifact_enums": run([sys.executable, str(ROOT / "scripts/run-artifact-tests.py")]),
    }
    return {
        name: {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
        for name, (code, out, err) in gates.items()
    }


def check_cognitive_gates():
    gates = {
        "capability_graph": run([sys.executable, str(ROOT / "scripts/build-capability-graph.py"), "--check"]),
        "pathfinder": run([sys.executable, str(ROOT / "scripts/run-pathfinder-tests.py"), "--no-telemetry"]),
        "invocation_telemetry": run([sys.executable, str(ROOT / "scripts/audit-invocation-telemetry.py"), "--json", "--enforce"]),
        "cognitive_integration": run([sys.executable, str(ROOT / "scripts/run-cognitive-tests.py")]),
        "dream_catalog": run([sys.executable, str(ROOT / "scripts/dream-runner.py"), "validate-catalog"]),
        "panel_runs": run([sys.executable, str(ROOT / "scripts/panel-runs.py"), "stats"]),
        "experience_quality_panel_smoke": run([sys.executable, str(ROOT / "scripts/panel-runs.py"), "smoke", "--panel", "experience-quality-panel"]),
    }
    return {
        name: {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
        for name, (code, out, err) in gates.items()
    }


def find_codex_cache_version() -> Path | None:
    if not CODEX_CACHE.exists():
        return None
    versions = [p for p in CODEX_CACHE.iterdir() if p.is_dir() and (p / ".codex-plugin" / "plugin.json").exists()]
    if not versions:
        return None
    return sorted(versions)[-1]


def find_codex_cache_versions() -> list[Path]:
    if not CODEX_CACHE.exists():
        return []
    versions = [p for p in CODEX_CACHE.iterdir() if p.is_dir() and (p / ".codex-plugin" / "plugin.json").exists()]
    if (CODEX_CACHE / ".codex-plugin" / "plugin.json").exists():
        versions.append(CODEX_CACHE)
    return sorted(versions, key=semver_key)


def find_claude_install() -> Path | None:
    for candidate in CLAUDE_INSTALL_CANDIDATES:
        if (candidate / ".claude-plugin" / "plugin.json").exists():
            return candidate
    return None


def find_claude_active_install() -> tuple[Path | None, dict[str, Any]]:
    data = load_json(CLAUDE_INSTALLED_PLUGINS)
    entries = ((data.get("plugins") or {}).get(CLAUDE_PLUGIN_ID) or [])
    paths: list[Path] = []
    for entry in entries:
        install_path = entry.get("installPath") if isinstance(entry, dict) else None
        if isinstance(install_path, str):
            paths.append(Path(install_path))
    existing = [p for p in paths if (p / ".claude-plugin" / "plugin.json").exists()]
    if existing:
        return existing[-1], {
            "ok": True,
            "installed_plugins_path": str(CLAUDE_INSTALLED_PLUGINS),
            "configured_paths": [str(p) for p in paths],
        }
    marketplace = find_claude_install()
    return marketplace, {
        "ok": False,
        "installed_plugins_path": str(CLAUDE_INSTALLED_PLUGINS),
        "configured_paths": [str(p) for p in paths],
        "fallback_marketplace_path": str(marketplace) if marketplace else None,
    }


def claude_plugins_list_status(expected: dict[str, Any]) -> dict[str, Any]:
    code, out, err = run(["claude", "plugins", "list"], timeout=30)
    text = "\n".join(part for part in (out, err) if part)
    expected_version = str(expected.get("version"))
    ok = (
        code == 0
        and CLAUDE_PLUGIN_ID in text
        and f"Version: {expected_version}" in text
        and "failed to load" not in text.lower()
        and "Status: ✘" not in text
    )
    return {
        "ok": ok,
        "stdout": out.strip(),
        "stderr": err.strip(),
    }


def check_package_runtime_target(expected: dict[str, Any]) -> dict[str, Any]:
    temp_root = Path(tempfile.mkdtemp(prefix="ultraprompt-scorecard-package-"))
    target = temp_root / "ultraprompt"
    checks: dict[str, Any] = {}
    try:
        code, out, err = run([sys.executable, str(ROOT / "scripts" / "package-plugin.py"), "--copy-to", str(target)], timeout=180)
        checks["copy"] = {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
        return runtime_target_status(
            "package",
            target,
            runtime="claude-code",
            expected=expected,
            next_action="python3 scripts/package-plugin.py --verify-only",
            checks=checks,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


def check_runtime_targets(target: str) -> dict:
    expected = source_expected()
    targets: dict[str, dict] = {
        "source": runtime_target_status(
            "source",
            ROOT,
            runtime="claude-code",
            expected=expected,
            checks={
                "validate_plugin": {"ok": True, "stdout": "source validation is covered by trust_gates.plugin_validation", "stderr": ""},
            },
        )
    }
    if target == "all":
        targets["package"] = check_package_runtime_target(expected)
        cache_versions = find_codex_cache_versions()
        cache_root = cache_versions[-1] if cache_versions else None
        if cache_root is None:
            targets["codex_cache"] = {
                "target": "codex_cache",
                "path": str(CODEX_CACHE),
                "runtime": "codex",
                "version": "missing",
                "skill_count": None,
                "agent_count": None,
                "command_count": None,
                "mcp_tool_count": None,
                "ok": False,
                "findings": ["Codex cache version directory not found"],
                "next_action": "bash scripts/install.sh codex",
                "checks": {"present": {"ok": False, "stdout": "", "stderr": "Codex cache version directory not found"}},
            }
        else:
            code, out, err = run(
                [sys.executable, str(cache_root / "scripts" / "validate-plugin.py"), "--target-runtime", "source", "--strict-runtime-files"],
                cwd=cache_root,
                timeout=180,
            )
            targets["codex_cache"] = runtime_target_status(
                "codex_cache",
                cache_root,
                runtime="codex",
                expected=expected,
                next_action="bash scripts/install.sh codex",
                checks={
                    "validate_plugin": {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()},
                    "discovered_candidates": {"ok": True, "versions": [str(p) for p in cache_versions]},
                },
            )
            if code != 0:
                targets["codex_cache"]["ok"] = False
                targets["codex_cache"]["findings"].append("validate-plugin failed for Codex cache")

        claude_root, installed_status = find_claude_active_install()
        if claude_root is None:
            targets["claude_code_install"] = {
                "target": "claude_code_install",
                "path": str(CLAUDE_INSTALLED_PLUGINS),
                "runtime": "claude-code",
                "version": "missing",
                "skill_count": None,
                "agent_count": None,
                "command_count": None,
                "mcp_tool_count": None,
                "ok": False,
                "findings": ["Claude Code active installed plugin cache not found"],
                "next_action": "bash scripts/install.sh claude-code",
                "checks": {"installed_plugins": installed_status},
            }
        else:
            code, out, err = run(
                [sys.executable, str(claude_root / "scripts" / "validate-plugin.py"), "--target-runtime", "claude", "--strict-runtime-files"],
                cwd=claude_root,
                timeout=180,
            )
            cli_status = claude_plugins_list_status(expected)
            targets["claude_code_install"] = runtime_target_status(
                "claude_code_install",
                claude_root,
                runtime="claude-code",
                expected=expected,
                next_action="bash scripts/install.sh claude-code",
                checks={
                    "installed_plugins": installed_status,
                    "validate_plugin": {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()},
                    "claude_plugins_list": cli_status,
                },
            )
            if not installed_status.get("ok"):
                targets["claude_code_install"]["ok"] = False
                targets["claude_code_install"]["findings"].append("Claude Code installed_plugins.json does not point at an active cache")
            if code != 0:
                targets["claude_code_install"]["ok"] = False
                targets["claude_code_install"]["findings"].append("validate-plugin failed for Claude Code install")
            if not cli_status.get("ok"):
                targets["claude_code_install"]["ok"] = False
                targets["claude_code_install"]["findings"].append("claude plugins list did not report a loaded current-version plugin")
    return targets


def gate_ok(gates: dict[str, Any], name: str) -> bool:
    return bool((gates.get(name) or {}).get("ok"))


def target_decomposition(scorecard_data: dict[str, Any]) -> dict[str, Any]:
    runtime_targets = scorecard_data.get("runtime_targets", {})
    trust = scorecard_data.get("trust_gates", {})
    cognitive = scorecard_data.get("cognitive_gates", {})
    return {
        "source": {"ok": bool((runtime_targets.get("source") or {}).get("ok")) and gate_ok(trust, "plugin_validation")},
        "package": {"ok": bool((runtime_targets.get("package") or {}).get("ok", True)) and gate_ok(trust, "package_verify")},
        "install_simulation": {"ok": gate_ok(trust, "install_simulation")},
        "active_codex_cache": {"ok": bool((runtime_targets.get("codex_cache") or {}).get("ok", scorecard_data.get("target") != "all"))},
        "active_claude_code_install": {"ok": bool((runtime_targets.get("claude_code_install") or {}).get("ok", scorecard_data.get("target") != "all"))},
        "telemetry": {"ok": gate_ok(cognitive, "invocation_telemetry")},
        "artifact": {"ok": gate_ok(trust, "artifact_enums")},
        "panel": {"ok": gate_ok(cognitive, "experience_quality_panel_smoke")},
    }


def normalized_scorecard_for_hash(scorecard_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "plugin_version": scorecard_data.get("plugin_version"),
        "target": scorecard_data.get("target"),
        "manifest": scorecard_data.get("manifest"),
        "discovery": scorecard_data.get("discovery"),
        "routing": scorecard_data.get("routing"),
        "safety": {
            "hook_fixtures": (scorecard_data.get("safety") or {}).get("hook_fixtures"),
            "hook_coverage_ok": ((scorecard_data.get("safety") or {}).get("hook_coverage") or {}).get("ok"),
        },
        "docs": scorecard_data.get("docs"),
        "trust_gates": {k: {"ok": v.get("ok")} for k, v in (scorecard_data.get("trust_gates") or {}).items()},
        "cognitive_gates": {k: {"ok": v.get("ok")} for k, v in (scorecard_data.get("cognitive_gates") or {}).items()},
        "runtime_targets": {
            k: {
                "ok": v.get("ok"),
                "version": v.get("version"),
                "skill_count": v.get("skill_count"),
                "agent_count": v.get("agent_count"),
                "command_count": v.get("command_count"),
                "mcp_tool_count": v.get("mcp_tool_count"),
                "findings": v.get("findings"),
            }
            for k, v in (scorecard_data.get("runtime_targets") or {}).items()
        },
        "conclusion": scorecard_data.get("conclusion"),
        "blockers": scorecard_data.get("blockers", []),
        "warnings": scorecard_data.get("warnings", []),
    }


def result_hash(scorecard_data: dict[str, Any]) -> str:
    payload = json.dumps(normalized_scorecard_for_hash(scorecard_data), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def annotate_freshness(scorecard: dict[str, Any], *, report_mode: str) -> None:
    s = scorecard["release_scorecard"]
    s["result_hash"] = result_hash(s)
    persisted_path = ROOT / "dist" / "release-scorecard.json"
    persisted = load_json(persisted_path)
    persisted_scorecard = persisted.get("release_scorecard") if isinstance(persisted.get("release_scorecard"), dict) else {}
    persisted_hash = persisted_scorecard.get("result_hash")
    if report_mode == "write":
        freshness = "current"
    elif not persisted_path.exists():
        freshness = "missing_persisted_report"
    elif persisted_scorecard.get("schema_version") != s.get("schema_version") or not persisted_hash:
        freshness = "stale_persisted_report"
    elif persisted_hash != s["result_hash"]:
        freshness = "stale_persisted_report"
    else:
        freshness = "current"
    s["freshness"] = freshness
    if report_mode == "write":
        s["persisted_report"] = {
            "path": str(persisted_path.relative_to(ROOT)),
            "schema_version": s.get("schema_version"),
            "generated_at": s.get("generated_at"),
            "generated_from_commit": s.get("generated_from_commit"),
            "target": s.get("target"),
            "conclusion": s.get("conclusion"),
            "result_hash": s.get("result_hash"),
        }
    else:
        s["persisted_report"] = {
            "path": str(persisted_path.relative_to(ROOT)),
            "schema_version": persisted_scorecard.get("schema_version"),
            "generated_at": persisted_scorecard.get("generated_at"),
            "generated_from_commit": persisted_scorecard.get("generated_from_commit"),
            "target": persisted_scorecard.get("target"),
            "conclusion": persisted_scorecard.get("conclusion"),
            "result_hash": persisted_hash,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Run read-only scorecard; do not write dist/release-scorecard.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--target", choices=["source", "all"], default="source",
                        help="Validation target scope. 'all' also validates package, active Codex cache, and active Claude Code install.")
    parser.add_argument("--write-report", action="store_true", help="Write dist/release-scorecard.json even with --check")
    args = parser.parse_args()

    report_mode = "write" if (args.write_report or not args.check) else "check"
    scorecard = {
        "release_scorecard": {
            "schema_version": 2,
            "generated_at": int(time.time()),
            "generated_from_commit": git_value(["rev-parse", "HEAD"]) or "unknown",
            "dirty_state": dirty_state(),
            "report_mode": report_mode,
            "plugin_version": plugin_version(),
            "target": args.target,
            "manifest": check_manifests(),
            "discovery": check_discovery(),
            "routing": check_routing(),
            "safety": check_safety(),
            "docs": check_docs(),
            "trust_gates": check_trust_gates(),
            "cognitive_gates": check_cognitive_gates(),
            "runtime_targets": check_runtime_targets(args.target),
            "conclusion": None,
        }
    }
    # Determine conclusion
    s = scorecard["release_scorecard"]
    blockers = []
    if not s["manifest"]["claude_valid"]: blockers.append("claude manifest invalid")
    if not s["manifest"]["codex_valid"]: blockers.append("codex manifest invalid")
    if s["safety"]["hook_fixtures"] != "pass": blockers.append("hook fixtures failing")
    if not s["safety"]["hook_coverage"].get("ok"): blockers.append("hook coverage matrix incomplete")
    if (s["routing"]["top3_accuracy"] or 0) < 100: blockers.append("router top-3 < 100%")
    for gate, result in s["trust_gates"].items():
        if not result["ok"]:
            blockers.append(f"{gate} failed")
    for gate, result in s["cognitive_gates"].items():
        if not result["ok"]:
            blockers.append(f"{gate} failed")
    for target_name, result in s["runtime_targets"].items():
        if not result.get("ok"):
            blockers.append(f"{target_name} runtime target failed")

    s["target_decomposition"] = target_decomposition(s)

    if blockers:
        s["conclusion"] = "blocked"
        s["blockers"] = blockers
    elif s["docs"]["stale_version_refs"] > 0:
        s["conclusion"] = "risky"
        s["warnings"] = [f"{s['docs']['stale_version_refs']} stale version refs"]
    else:
        s["conclusion"] = "ready"

    annotate_freshness(scorecard, report_mode=report_mode)
    if s["freshness"] != "current":
        s.setdefault("warnings", []).append(s["freshness"])

    if args.json:
        print(json.dumps(scorecard, indent=2))
    else:
        print(f"=== Release Scorecard (V{s['plugin_version']}) ===")
        print(f"Plugin version:  {s['plugin_version']}")
        print(f"Generated from:  {s['generated_from_commit']} ({s['dirty_state']})")
        print(f"Target:          {s['target']}")
        print(f"Report mode:     {s['report_mode']} freshness={s['freshness']}")
        print(f"Manifests:       claude={s['manifest']['claude_valid']} codex={s['manifest']['codex_valid']}")
        print(f"Discovery:       skills={s['discovery']['skills_discovered']} agents={s['discovery']['agents_discovered']} commands={s['discovery']['commands_discovered']}")
        print(f"Routing:         top-1={s['routing']['top1_accuracy']}% top-3={s['routing']['top3_accuracy']}%")
        print(f"Safety:          hooks={s['safety']['hook_fixtures']}")
        print(f"Hook coverage:   {s['safety']['hook_coverage'].get('covered', 0)}/{s['safety']['hook_coverage'].get('registered', 0)}")
        print(f"Docs:            stale_refs={s['docs']['stale_version_refs']}")
        print(f"Trust gates:     {sum(1 for g in s['trust_gates'].values() if g['ok'])}/{len(s['trust_gates'])}")
        print(f"Cognitive gates: {sum(1 for g in s['cognitive_gates'].values() if g['ok'])}/{len(s['cognitive_gates'])}")
        print(f"Runtime targets: {sum(1 for g in s['runtime_targets'].values() if g.get('ok'))}/{len(s['runtime_targets'])}")
        for target_name, result in s["runtime_targets"].items():
            state = "ok" if result.get("ok") else "blocked"
            version = result.get("version", "unknown")
            counts = f"{result.get('skill_count')} skills / {result.get('agent_count')} agents / {result.get('command_count')} commands"
            print(f"  - {target_name}: {state} version={version} {counts}")
            for finding in result.get("findings", [])[:3]:
                print(f"    finding: {finding}")
            if result.get("next_action") and not result.get("ok"):
                print(f"    next_action: {result['next_action']}")
        print()
        print(f"CONCLUSION:      {s['conclusion'].upper()}")
        if s.get("blockers"): print(f"  Blockers: {s['blockers']}")
        if s.get("warnings"): print(f"  Warnings: {s['warnings']}")

    if args.write_report or not args.check:
        json_path = ROOT / "dist/release-scorecard.json"
        json_path.parent.mkdir(exist_ok=True)
        json.dump(scorecard, open(json_path, "w"), indent=2)
        if not args.json:
            print(f"\nFull report: {json_path}")

    return 0 if s["conclusion"] != "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
