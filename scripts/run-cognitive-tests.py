#!/usr/bin/env python3
"""V8 cognitive integration tests using an isolated temp state dir."""
from __future__ import annotations

import importlib.util
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


def load_script(rel: str, name: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
        trigger_event = run([
            "cognitive-event-log.py", "write", "route_trigger_plan_emitted",
            "--field", "producer=route_trigger_plan",
            "--field", "telemetry_source=runtime",
            "--field", "intent=fixture routing plan",
            "--field", "skill=pathfinding-invocation-review",
        ], env)
        assert_ok(trigger_event, "route trigger telemetry event write", failures)
        ev_stats = run(["cognitive-event-log.py", "stats"], env)
        assert_ok(ev_stats, "event stats", failures)

        codex_ledger = tmp_root / f"codex-ledger-{stamp}"
        codex_env = env.copy()
        codex_env["ULTRAPROMPT_LEDGER_DIR"] = str(codex_ledger)
        codex_env["CODEX_SESSION_ID"] = "codex-test-session"
        codex_env.pop("CLAUDE_SESSION_ID", None)
        codex_write = run(["ledger-v2.py", "write", "agent_dispatch", "--field", "agent=ultraprompt:reviewer"], codex_env)
        assert_ok(codex_write, "codex runtime ledger write", failures)
        codex_events = list(codex_ledger.glob("events-*.jsonl"))
        if not codex_events or '"runtime": "codex"' not in codex_events[0].read_text(encoding="utf-8"):
            failures.append({"label": "ledger records codex runtime", "result": {"files": [str(p) for p in codex_events]}})
        if codex_events:
            first_event = json.loads(codex_events[0].read_text(encoding="utf-8").splitlines()[0])
            for field in ("runtime", "session_id", "source", "repo", "worktree", "plugin_version"):
                if not first_event.get(field):
                    failures.append({"label": "ledger normalized metadata fields", "result": first_event})
                    break

        old_process_env = {key: os.environ.get(key) for key in ("ULTRAPROMPT_LEDGER_DIR", "CODEX_SESSION_ID", "CLAUDE_SESSION_ID", "CODEX_VERSION", "CODEX_HOME")}
        os.environ["ULTRAPROMPT_LEDGER_DIR"] = str(codex_ledger)
        os.environ["CODEX_SESSION_ID"] = "codex-test-session"
        os.environ.pop("CLAUDE_SESSION_ID", None)
        try:
            mcp_ledger_mod = load_script("mcp/ultraprompt_meta.py", "ultraprompt_meta_ledger_test")
            mcp_ledger_mod._ledger_write_call("claim_check", {"trace_id": "trace_fixture"}, 7, True, extra={"passed": True})
        finally:
            for key, value in old_process_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        mcp_event_seen = False
        for ledger_path in codex_ledger.glob("events-*.jsonl"):
            for line in ledger_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("type") == "mcp_tool_call" and event.get("tool") == "claim_check":
                    mcp_event_seen = all(event.get(field) for field in ("runtime", "session_id", "trace_id", "tool", "source", "repo", "worktree", "plugin_version"))
        if not mcp_event_seen:
            failures.append({"label": "mcp ledger event has normalized runtime fields", "result": {"ledger": str(codex_ledger)}})

        claude_ledger = tmp_root / f"claude-ledger-{stamp}"
        claude_env = env.copy()
        claude_env["ULTRAPROMPT_LEDGER_DIR"] = str(claude_ledger)
        claude_env["CLAUDE_SESSION_ID"] = "claude-test-session"
        for key in ("CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_HOME"):
            claude_env.pop(key, None)
        claude_write = run(["ledger-v2.py", "write", "skill_invocation", "--field", "skill=ultraprompt:review"], claude_env)
        assert_ok(claude_write, "claude runtime ledger write", failures)
        claude_events = list(claude_ledger.glob("events-*.jsonl"))
        if not claude_events or '"runtime": "claude-code"' not in claude_events[0].read_text(encoding="utf-8"):
            failures.append({"label": "ledger records claude-code runtime", "result": {"files": [str(p) for p in claude_events]}})

        audit_mod = load_script("scripts/audit-invocation-telemetry.py", "audit_invocation_telemetry")
        scorecard_mod = load_script("scripts/release-scorecard.py", "release_scorecard_test")
        generated_mod = load_script("scripts/generated-artifacts.py", "generated_artifacts_test")
        self_improve_mod = load_script("scripts/self-improve.py", "self_improve_test")
        if scorecard_mod.classify_gate_blocker("invocation_telemetry", 1, "", "") != "live_adoption_blocker":
            failures.append({"label": "scorecard classifies telemetry adoption blocker", "result": {}})
        if scorecard_mod.classify_gate_blocker("pathfinder", -124, "", "timeout after 1s") != "harness_timeout":
            failures.append({"label": "scorecard classifies harness timeout", "result": {}})
        if scorecard_mod.classify_gate_blocker("self_improvement_canary", 1, "", "self-improvement regression") != "self_improvement_regression":
            failures.append({"label": "scorecard classifies self-improvement regression", "result": {}})
        artifact_class = generated_mod.classify_artifact_check("catalog_metadata", {
            "ok": False,
            "exit_code": 1,
            "stdout": "dist/catalog-metadata.json is stale; run scripts/build-catalog-metadata.py",
            "stderr": "",
        })
        if artifact_class.get("failure_kind") != "generated_artifact_drift":
            failures.append({"label": "generated artifact drift classified", "result": artifact_class})
        status, _ = audit_mod.classify_handoff_status("[Truncated. Full output: /tmp/task.output]")
        if status != "truncated":
            failures.append({"label": "truncated handoff classified", "result": {"status": status}})
        status, _ = audit_mod.classify_handoff_status("The reviewer agent returned only a partial finding.")
        if status != "truncated":
            failures.append({"label": "partial finding handoff classified", "result": {"status": status}})
        status, _ = audit_mod.classify_handoff_status("")
        if status != "complete":
            failures.append({"label": "blank non-agent event is not treated as empty handoff", "result": {"status": status}})

        codex_sessions = tmp_root / f"codex-sessions-{stamp}"
        codex_sessions.mkdir(parents=True, exist_ok=True)
        session_file = codex_sessions / "fixture.jsonl"
        session_file.write_text(
            json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "payload": {
                    "name": "mcp__ultraprompt_meta__claim_check",
                    "content": "$ultraprompt:review [Truncated. Full output: /tmp/full]",
                },
            }) + "\n" + json.dumps({
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "payload": {
                    "type": "function_call",
                    "name": "ultraprompt_meta.route_feedback",
                    "arguments": {"intent": "fixture"},
                },
            }) + "\n",
            encoding="utf-8",
        )
        old_codex_sessions = os.environ.get("ULTRAPROMPT_CODEX_SESSIONS_DIR")
        os.environ["ULTRAPROMPT_CODEX_SESSIONS_DIR"] = str(codex_sessions)
        try:
            codex_activity = audit_mod.read_codex_activity(1)
        finally:
            if old_codex_sessions is None:
                os.environ.pop("ULTRAPROMPT_CODEX_SESSIONS_DIR", None)
            else:
                os.environ["ULTRAPROMPT_CODEX_SESSIONS_DIR"] = old_codex_sessions
        if codex_activity["skill_mentions"].get("ultraprompt:review", 0) < 1 or codex_activity["mcp_tool_calls"].get("claim_check", 0) < 1 or codex_activity["mcp_tool_calls"].get("route_feedback", 0) < 1 or not codex_activity["handoffs"]:
            failures.append({"label": "codex activity parser extracts skills mcp and truncation", "result": codex_activity})

        generated_check = run(["generated-artifacts.py", "check", "--json"], env)
        assert_ok(generated_check, "generated artifact preflight", failures)

        graph = run(["build-capability-graph.py", "--check"], env)
        assert_ok(graph, "capability graph freshness", failures)

        pathfinder = run(["run-pathfinder-tests.py", "--json"], env)
        assert_ok(pathfinder, "pathfinder golden tests", failures)

        review_path = run(["pathfinder.py", "pathfind", "--intent", "review this diff before merge", "--no-telemetry"], env)
        assert_ok(review_path, "pathfinder review handoff", failures)
        review_envelope = (((review_path.get("json") or {}).get("path") or {}).get("routing_envelope") or {})
        review_dispatches = review_envelope.get("dispatches") or []
        if not review_dispatches or review_dispatches[0].get("handoff_policy", {}).get("mode") != "artifact_first":
            failures.append({"label": "routing envelope includes artifact-first handoff", "result": review_envelope})
        if not review_dispatches or not review_dispatches[0].get("handoff_contract_status", {}).get("ok"):
            failures.append({"label": "routing envelope validates handoff contract", "result": review_envelope})

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

        old_state = os.environ.get("ULTRAPROMPT_STATE_DIR")
        os.environ["ULTRAPROMPT_STATE_DIR"] = tmp
        try:
            mcp_mod = load_script("mcp/ultraprompt_meta.py", "ultraprompt_meta_test")
            feedback = mcp_mod.tool_route_feedback({
                "intent": "review this diff",
                "outcome": "failed",
                "skill": "review",
                "agent": "ultraprompt:reviewer",
                "handoff_status": "truncated",
                "failure_kind": "partial finding",
                "artifact_path": str(Path(tmp) / "handoff.md"),
                "tool_count": 32,
                "token_count": 70800,
                "evidence_refs": ["fixture"],
            })
            feedback_data = json.loads(feedback["content"][0]["text"])
        finally:
            if old_state is None:
                os.environ.pop("ULTRAPROMPT_STATE_DIR", None)
            else:
                os.environ["ULTRAPROMPT_STATE_DIR"] = old_state
        if not feedback_data.get("learning_candidate", {}).get("ok"):
            failures.append({"label": "route feedback creates handoff learning candidate", "result": feedback_data})
        grouped = run(["learning-queue.py", "list", "--kind", "route_update", "--grouped"], env)
        assert_ok(grouped, "learning grouped route candidates", failures)
        grouped_json = grouped.get("json") or {}
        candidates = grouped_json.get("candidates") or []
        if not grouped_json.get("candidate_groups") or not candidates or not candidates[0].get("policy_preview") or not candidates[0].get("replay_impact"):
            failures.append({"label": "learning candidates include grouping preview and replay impact", "result": grouped_json})

        evidence = {
            "audit": {
                "candidate_groups": {
                    "groups": [
                        {"kind": "explore_fallback", "evidence_count": 12},
                        {"kind": "agent_handoff", "evidence_count": 9},
                    ]
                },
                "runtime_events": {"by_runtime": {"unknown": 3}},
                "activation_gaps": {"skills_never_invoked": ["llm-eval-design"], "agents_never_dispatched": ["evaluator"]},
            }
        }
        hypotheses = self_improve_mod.derive_hypotheses(evidence, "all")
        required_hypothesis_kinds = {"route_update", "agent_contract_update", "telemetry_parser_update", "eval_case_update"}
        if not hypotheses or not required_hypothesis_kinds.issubset({h.get("kind") for h in hypotheses}):
            failures.append({"label": "self-improve derives hypotheses from telemetry evidence", "result": hypotheses})

        if hypotheses:
            old_state_for_self = os.environ.get("ULTRAPROMPT_STATE_DIR")
            os.environ["ULTRAPROMPT_STATE_DIR"] = tmp
            try:
                materialized = self_improve_mod.materialize_learning_candidate(hypotheses[0], "improve_fixture")
            finally:
                if old_state_for_self is None:
                    os.environ.pop("ULTRAPROMPT_STATE_DIR", None)
                else:
                    os.environ["ULTRAPROMPT_STATE_DIR"] = old_state_for_self
            candidate = materialized.get("candidate") or {}
            if not materialized.get("ok") or not candidate.get("auto_apply") or not candidate.get("mutation_scope"):
                failures.append({"label": "self-improve materializes auto-apply learning candidate", "result": materialized})
        else:
            failures.append({"label": "self-improve materializes auto-apply learning candidate", "result": {"error": "no_hypotheses"}})

        source_repo = tmp_root / f"self-improve-source-{stamp}"
        source_repo.mkdir(parents=True, exist_ok=True)
        source_file = source_repo / "src" / "example.txt"
        source_file.parent.mkdir(parents=True, exist_ok=True)
        source_file.write_text("before", encoding="utf-8")
        rollback_entries = self_improve_mod.apply_source_changes("improve_fixture", source_repo, [{"path": "src/example.txt", "content": "after"}])
        if source_file.read_text(encoding="utf-8") != "after":
            failures.append({"label": "self-improve applies source patch", "result": rollback_entries})
        rollback_result = self_improve_mod.rollback_from_manifest({"entries": rollback_entries})
        if source_file.read_text(encoding="utf-8") != "before":
            failures.append({"label": "self-improve rollback restores source patch", "result": rollback_result})

    result = command_result(not failures, failures=failures, tests=[
        "memory schema/privacy/query/status/export",
        "cognitive event write/query/stats",
        "dual-runtime ledger metadata",
        "mcp ledger normalized metadata",
        "codex activity and handoff parsing",
        "release gate and generated artifact classification",
        "generated artifact preflight",
        "route trigger telemetry event write",
        "capability graph freshness",
        "pathfinder golden cases",
        "artifact-first routing envelope",
        "handoff contract status",
        "dream no-repo-mutation",
        "learning approve/apply/revert",
        "route feedback learning candidate",
        "grouped learning candidate preview",
        "self-improvement hypothesis ranking",
        "self-improvement auto-apply materialization",
        "self-improvement source rollback",
    ])
    print_json(result)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
