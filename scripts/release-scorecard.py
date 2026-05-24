#!/usr/bin/env python3
"""V8.7.0: Release scorecard.

Generates a release-readiness scorecard for the plugin itself. Covers manifest,
discovery, routing, safety, docs, install dimensions.

Outputs YAML for downstream consumption + human-readable summary.
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
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


def check_manifests():
    claude_p = ROOT / ".claude-plugin/plugin.json"
    codex_p = ROOT / ".codex-plugin/plugin.json"
    claude_ok = False
    codex_ok = False
    try:
        if claude_p.exists():
            d = json.load(open(claude_p))
            claude_ok = "name" in d and "version" in d
    except Exception:
        pass
    try:
        if codex_p.exists():
            d = json.load(open(codex_p))
            codex_ok = "name" in d and "version" in d
    except Exception:
        pass
    return {"claude_valid": claude_ok, "codex_valid": codex_ok}


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
        "catalog_consistency": run([sys.executable, str(ROOT / "scripts/audit-catalog-consistency.py"), "--json"]),
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
        "pathfinder": run([sys.executable, str(ROOT / "scripts/run-pathfinder-tests.py")]),
        "cognitive_integration": run([sys.executable, str(ROOT / "scripts/run-cognitive-tests.py")]),
        "dream_catalog": run([sys.executable, str(ROOT / "scripts/dream-runner.py"), "validate-catalog"]),
    }
    return {
        name: {"ok": code == 0, "stdout": out.strip(), "stderr": err.strip()}
        for name, (code, out, err) in gates.items()
    }


def main():
    scorecard = {
        "release_scorecard": {
            "schema_version": 1,
            "plugin_version": plugin_version(),
            "manifest": check_manifests(),
            "discovery": check_discovery(),
            "routing": check_routing(),
            "safety": check_safety(),
            "docs": check_docs(),
            "trust_gates": check_trust_gates(),
            "cognitive_gates": check_cognitive_gates(),
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

    if blockers:
        s["conclusion"] = "blocked"
        s["blockers"] = blockers
    elif s["docs"]["stale_version_refs"] > 0:
        s["conclusion"] = "risky"
        s["warnings"] = [f"{s['docs']['stale_version_refs']} stale version refs"]
    else:
        s["conclusion"] = "ready"

    # Human-readable summary
    print(f"=== Release Scorecard (V{s['plugin_version']}) ===")
    print(f"Plugin version:  {s['plugin_version']}")
    print(f"Manifests:       claude={s['manifest']['claude_valid']} codex={s['manifest']['codex_valid']}")
    print(f"Discovery:       skills={s['discovery']['skills_discovered']} agents={s['discovery']['agents_discovered']} commands={s['discovery']['commands_discovered']}")
    print(f"Routing:         top-1={s['routing']['top1_accuracy']}% top-3={s['routing']['top3_accuracy']}%")
    print(f"Safety:          hooks={s['safety']['hook_fixtures']}")
    print(f"Hook coverage:   {s['safety']['hook_coverage'].get('covered', 0)}/{s['safety']['hook_coverage'].get('registered', 0)}")
    print(f"Docs:            stale_refs={s['docs']['stale_version_refs']}")
    print(f"Trust gates:     {sum(1 for g in s['trust_gates'].values() if g['ok'])}/{len(s['trust_gates'])}")
    print(f"Cognitive gates: {sum(1 for g in s['cognitive_gates'].values() if g['ok'])}/{len(s['cognitive_gates'])}")
    print()
    print(f"CONCLUSION:      {s['conclusion'].upper()}")
    if s.get("blockers"): print(f"  Blockers: {s['blockers']}")
    if s.get("warnings"): print(f"  Warnings: {s['warnings']}")

    # Emit JSON for machine consumption
    json_path = ROOT / "dist/release-scorecard.json"
    json_path.parent.mkdir(exist_ok=True)
    json.dump(scorecard, open(json_path, "w"), indent=2)
    print(f"\nFull report: {json_path}")

    return 0 if s["conclusion"] != "blocked" else 1


if __name__ == "__main__":
    sys.exit(main())
