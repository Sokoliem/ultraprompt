#!/usr/bin/env python3
"""V8.2.0: Release scorecard.

Generates a release-readiness scorecard for the plugin itself. Covers manifest,
discovery, routing, safety, docs, install dimensions.

Outputs YAML for downstream consumption + human-readable summary.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEX_CACHE = Path.home() / ".codex" / "plugins" / "cache" / "local-marketplace" / "ultraprompt"


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


def resolve_manifest_ref(ref: str) -> Path:
    rel = ref[2:] if ref.startswith("./") else ref
    return ROOT / rel


def manifest_status(path: Path) -> dict:
    data = load_json(path)
    missing_fields = [field for field in ("name", "version", "description") if field not in data]
    missing_refs = []
    for field in ("mcpServers", "hooks", "outputStyles"):
        ref = data.get(field)
        if isinstance(ref, str) and not resolve_manifest_ref(ref).exists():
            missing_refs.append({"field": field, "path": ref})
    return {
        "path": str(path.relative_to(ROOT)),
        "valid": path.exists() and not missing_fields and not missing_refs,
        "present": path.exists(),
        "missing_fields": missing_fields,
        "missing_references": missing_refs,
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


def check_runtime_targets(target: str) -> dict:
    targets: dict[str, dict] = {
        "source": {
            "path": str(ROOT),
            "ok": True,
            "checks": {
                "validate_plugin": {"ok": True, "stdout": "source validation is covered by trust_gates.plugin_validation", "stderr": ""},
            },
        }
    }
    if target == "all":
        cache_root = find_codex_cache_version()
        if cache_root is None:
            targets["codex_cache"] = {
                "path": str(CODEX_CACHE),
                "ok": False,
                "checks": {"present": {"ok": False, "stdout": "", "stderr": "Codex cache version directory not found"}},
            }
        else:
            code, out, err = run(
                [sys.executable, str(cache_root / "scripts" / "validate-plugin.py"), "--target-runtime", "source", "--strict-runtime-files"],
                cwd=cache_root,
                timeout=180,
            )
            targets["codex_cache"] = {
                "path": str(cache_root),
                "ok": code == 0,
                "checks": {
                    "validate_plugin": {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
                },
            }
    return targets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Run read-only scorecard; do not write dist/release-scorecard.json")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--target", choices=["source", "all"], default="source",
                        help="Validation target scope. 'all' also validates the active Codex cache.")
    parser.add_argument("--write-report", action="store_true", help="Write dist/release-scorecard.json even with --check")
    args = parser.parse_args()

    scorecard = {
        "release_scorecard": {
            "schema_version": 1,
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

    if blockers:
        s["conclusion"] = "blocked"
        s["blockers"] = blockers
    elif s["docs"]["stale_version_refs"] > 0:
        s["conclusion"] = "risky"
        s["warnings"] = [f"{s['docs']['stale_version_refs']} stale version refs"]
    else:
        s["conclusion"] = "ready"

    if args.json:
        print(json.dumps(scorecard, indent=2))
    else:
        print(f"=== Release Scorecard (V{s['plugin_version']}) ===")
        print(f"Plugin version:  {s['plugin_version']}")
        print(f"Target:          {s['target']}")
        print(f"Manifests:       claude={s['manifest']['claude_valid']} codex={s['manifest']['codex_valid']}")
        print(f"Discovery:       skills={s['discovery']['skills_discovered']} agents={s['discovery']['agents_discovered']} commands={s['discovery']['commands_discovered']}")
        print(f"Routing:         top-1={s['routing']['top1_accuracy']}% top-3={s['routing']['top3_accuracy']}%")
        print(f"Safety:          hooks={s['safety']['hook_fixtures']}")
        print(f"Hook coverage:   {s['safety']['hook_coverage'].get('covered', 0)}/{s['safety']['hook_coverage'].get('registered', 0)}")
        print(f"Docs:            stale_refs={s['docs']['stale_version_refs']}")
        print(f"Trust gates:     {sum(1 for g in s['trust_gates'].values() if g['ok'])}/{len(s['trust_gates'])}")
        print(f"Cognitive gates: {sum(1 for g in s['cognitive_gates'].values() if g['ok'])}/{len(s['cognitive_gates'])}")
        print(f"Runtime targets: {sum(1 for g in s['runtime_targets'].values() if g.get('ok'))}/{len(s['runtime_targets'])}")
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
