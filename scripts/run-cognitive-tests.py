#!/usr/bin/env python3
"""V8 cognitive integration tests using an isolated temp state dir."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cognitive_common import ROOT, command_result, print_json


def run(cmd: list[str], env: dict[str, str], timeout: int = 120) -> dict:
    proc = subprocess.run([sys.executable, str(ROOT / "scripts" / cmd[0]), *cmd[1:]], cwd=ROOT, capture_output=True, text=True, env=env, timeout=timeout)
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        parsed = None
    return {"cmd": " ".join(cmd), "exit": proc.returncode, "ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr, "json": parsed}


def assert_ok(result: dict, label: str, failures: list[dict]) -> None:
    if not result["ok"]:
        failures.append({"label": label, "result": {k: v for k, v in result.items() if k != "stdout" or len(v) < 2000}})


def main() -> int:
    failures: list[dict] = []
    tmp_root = Path(os.environ.get("ULTRAPROMPT_TEST_TMP") or (ROOT / ".test-tmp"))
    tmp_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    tmp = str(tmp_root / f"ultraprompt-v8-{stamp}")
    Path(tmp).mkdir(parents=True, exist_ok=True)
    if True:
        env = os.environ.copy()
        env["ULTRAPROMPT_STATE_DIR"] = tmp
        env["ULTRAPROMPT_STATE_DIR"] = tmp
        init = run(["memory-store.py", "init"], env)
        assert_ok(init, "memory init", failures)

        invalid = run(["memory-store.py", "write-candidate", "--kind", "repo_fact", "--scope", "repo", "--text", "token=sk-abcdefghijklmnopqrstuvwxyz", "--repo", "fixture"], env)
        if invalid["ok"] or "contains_secret_blocked" not in invalid["stdout"]:
            failures.append({"label": "secret memory blocked", "result": invalid})

        candidate = run([
            "memory-store.py", "write-candidate", "--kind", "repo_fact", "--scope", "repo",
            "--text", "The fixture repo uses Powershell-friendly commands.",
            "--repo", "fixture", "--entity", "commands", "--evidence", "file:README.md",
        ], env)
        assert_ok(candidate, "memory candidate write", failures)
        candidate_id = ((candidate.get("json") or {}).get("memory") or {}).get("id", "")

        no_evidence = run([
            "memory-store.py", "write-candidate", "--kind", "repo_fact", "--scope", "repo",
            "--text", "This candidate intentionally has no evidence.",
            "--repo", "fixture",
        ], env)
        assert_ok(no_evidence, "memory candidate without evidence write", failures)
        no_evidence_id = ((no_evidence.get("json") or {}).get("memory") or {}).get("id", "")
        promote_no_evidence = run(["memory-store.py", "promote", no_evidence_id], env)
        if promote_no_evidence["ok"]:
            failures.append({"label": "promotion without durable evidence fails for non-preference", "result": promote_no_evidence})

        promoted = run(["memory-store.py", "promote", candidate_id, "--evidence", "file:README.md"], env)
        assert_ok(promoted, "memory promotion", failures)

        query = run(["memory-store.py", "query", "--text", "Powershell", "--repo", "fixture"], env)
        assert_ok(query, "memory query", failures)
        if query["ok"] and not (query["json"] or {}).get("memories"):
            failures.append({"label": "memory query returns active memory", "result": query})

        active_id = ((promoted.get("json") or {}).get("memory") or {}).get("id", "")
        stale = run(["memory-store.py", "status", active_id, "stale", "--reason", "test"], env)
        assert_ok(stale, "memory stale status", failures)
        filtered = run(["memory-store.py", "query", "--text", "Powershell", "--repo", "fixture"], env)
        if filtered["ok"] and (filtered["json"] or {}).get("memories"):
            failures.append({"label": "stale memory excluded by default", "result": filtered})

        ev = run(["cognitive-event-log.py", "write", "route_outcome", "--field", "intent=build docs", "--field", "outcome=accepted"], env)
        assert_ok(ev, "event write", failures)
        ev_stats = run(["cognitive-event-log.py", "stats"], env)
        assert_ok(ev_stats, "event stats", failures)

        graph = run(["build-capability-graph.py", "--check"], env)
        assert_ok(graph, "capability graph freshness", failures)

        pathfinder = run(["run-pathfinder-tests.py", "--json"], env)
        assert_ok(pathfinder, "pathfinder golden tests", failures)

        repo = tmp_root / f"ultraprompt-repo-{stamp}"
        repo.mkdir(parents=True, exist_ok=True)
        if True:
            marker = repo / "marker.txt"
            marker.write_text("before", encoding="utf-8")
            dream = run(["dream-runner.py", "run", "session-compaction", "--repo", str(repo)], env)
            assert_ok(dream, "dream session compaction", failures)
            if marker.read_text(encoding="utf-8") != "before":
                failures.append({"label": "dream no repo mutation", "result": {"marker": marker.read_text(encoding="utf-8")}})

        learning = run([
            "learning-queue.py", "add", "--kind", "route_update", "--title", "Prefer build for fixture",
            "--payload-json", "{\"intent_pattern\":\"fixture build\",\"skill\":\"build\",\"weight_delta\":0.1}",
        ], env)
        assert_ok(learning, "learning add", failures)
        learn_id = ((learning.get("json") or {}).get("candidate") or {}).get("id", "")
        approve = run(["learning-queue.py", "approve", learn_id], env)
        assert_ok(approve, "learning approve", failures)
        apply = run(["learning-queue.py", "apply", learn_id], env, timeout=180)
        assert_ok(apply, "learning apply with validation", failures)
        revert = run(["learning-queue.py", "revert", learn_id], env)
        assert_ok(revert, "learning revert", failures)

    result = command_result(not failures, failures=failures, tests=[
        "memory schema/privacy/query/status/export",
        "cognitive event write/query/stats",
        "capability graph freshness",
        "pathfinder golden cases",
        "dream no-repo-mutation",
        "learning approve/apply/revert",
    ])
    print_json(result)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
