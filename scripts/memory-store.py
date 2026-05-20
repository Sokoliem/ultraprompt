#!/usr/bin/env python3
"""Typed local long-term memory store for Ultraprompt V8."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

from cognitive_common import (
    append_jsonl,
    command_result,
    data_dir,
    pii_findings,
    print_json,
    redact_text,
    secret_findings,
    sortable_id,
    utc_now,
)

KINDS = {
    "episodic",
    "repo_fact",
    "repo_pattern",
    "procedure",
    "route_outcome",
    "user_preference",
    "project_preference",
    "gap_memory",
    "ecosystem_observation",
    "dream_hypothesis",
}
SCOPES = {"user", "repo", "project", "plugin", "global"}
STATUSES = {"candidate", "active", "stale", "contradicted", "retired", "quarantined", "deleted"}
PRIVACY = {"metadata", "local_only", "contains_pii", "redacted"}
EVIDENCE_KINDS = {"event", "file", "artifact", "ledger", "user_confirmation", "dream_report", "gap", "route_feedback"}
PREFERENCE_KINDS = {"user_preference", "project_preference"}


def db_path() -> Path:
    return data_dir("memory") / "memory.db"


def log_path() -> Path:
    return data_dir("memory") / "memory.jsonl"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    migrate(con)
    return con


def migrate(con: sqlite3.Connection) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS migrations (
          version INTEGER PRIMARY KEY,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS memories (
          id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          kind TEXT NOT NULL,
          scope TEXT NOT NULL,
          privacy TEXT NOT NULL,
          text TEXT NOT NULL,
          repo TEXT,
          project TEXT,
          entity TEXT,
          confidence REAL NOT NULL,
          importance REAL NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          stale_after_days INTEGER,
          source TEXT,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          evidence_json TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS memory_entities (
          memory_id TEXT NOT NULL,
          entity TEXT NOT NULL,
          FOREIGN KEY(memory_id) REFERENCES memories(id)
        );
        CREATE TABLE IF NOT EXISTS memory_evidence (
          memory_id TEXT NOT NULL,
          kind TEXT NOT NULL,
          ref TEXT NOT NULL,
          note TEXT,
          created_at TEXT NOT NULL,
          FOREIGN KEY(memory_id) REFERENCES memories(id)
        );
        CREATE TABLE IF NOT EXISTS memory_revisions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          memory_id TEXT NOT NULL,
          ts TEXT NOT NULL,
          actor TEXT NOT NULL,
          action TEXT NOT NULL,
          before_json TEXT,
          after_json TEXT,
          reason TEXT,
          FOREIGN KEY(memory_id) REFERENCES memories(id)
        );
        CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
        CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
        CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
        CREATE INDEX IF NOT EXISTS idx_memories_repo ON memories(repo);
        CREATE INDEX IF NOT EXISTS idx_memory_entities_entity ON memory_entities(entity);
        """
    )
    con.execute("INSERT OR IGNORE INTO migrations(version, applied_at) VALUES(1, ?)", (utc_now(),))
    con.commit()


def parse_evidence(values: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for value in values:
        if ":" not in value:
            raise ValueError(f"evidence must be KIND:REF: {value}")
        kind, ref = value.split(":", 1)
        kind = kind.strip()
        ref = ref.strip()
        if kind not in EVIDENCE_KINDS:
            raise ValueError(f"invalid evidence kind: {kind}")
        if not ref:
            raise ValueError("evidence ref is required")
        out.append({"kind": kind, "ref": ref})
    return out


def validate_common(kind: str, scope: str, privacy: str, text: str, evidence: list[dict[str, str]]) -> None:
    if kind not in KINDS:
        raise ValueError(f"invalid memory kind: {kind}")
    if scope not in SCOPES:
        raise ValueError(f"invalid memory scope: {scope}")
    if privacy not in PRIVACY:
        raise ValueError(f"invalid privacy class: {privacy}")
    if not text.strip():
        raise ValueError("memory text is required")
    if secret_findings(text):
        raise ValueError("contains_secret_blocked")
    if pii_findings(text) and privacy != "contains_pii":
        raise ValueError("contains_pii_requires_privacy_class")
    for item in evidence:
        if item.get("kind") not in EVIDENCE_KINDS:
            raise ValueError(f"invalid evidence kind: {item.get('kind')}")


def row_to_dict(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    for key in ("metadata_json", "evidence_json"):
        raw = data.pop(key, "{}" if key == "metadata_json" else "[]")
        try:
            data[key.replace("_json", "")] = json.loads(raw or ("{}" if key == "metadata_json" else "[]"))
        except json.JSONDecodeError:
            data[key.replace("_json", "")] = {} if key == "metadata_json" else []
    return data


def revision(con: sqlite3.Connection, memory_id: str, action: str, *, actor: str = "cli", before: Any = None, after: Any = None, reason: str = "") -> None:
    con.execute(
        "INSERT INTO memory_revisions(memory_id, ts, actor, action, before_json, after_json, reason) VALUES(?,?,?,?,?,?,?)",
        (
            memory_id,
            utc_now(),
            actor,
            action,
            json.dumps(before, sort_keys=True) if before is not None else None,
            json.dumps(after, sort_keys=True) if after is not None else None,
            reason,
        ),
    )


def write_event(event_type: str, payload: dict[str, Any]) -> None:
    script = Path(__file__).with_name("cognitive-event-log.py")
    try:
        subprocess.run(
            [sys.executable, str(script), "write", event_type, "--json", json.dumps(payload), "--privacy", "metadata"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        pass


def insert_memory(con: sqlite3.Connection, memory: dict[str, Any], *, actor: str, reason: str) -> dict[str, Any]:
    now = utc_now()
    memory = {
        "id": memory.get("id") or sortable_id("memcand"),
        "status": memory.get("status", "candidate"),
        "created_at": memory.get("created_at") or now,
        "updated_at": now,
        "metadata": memory.get("metadata") or {},
        "evidence": memory.get("evidence") or [],
        **memory,
    }
    con.execute(
        """
        INSERT INTO memories(
          id,status,kind,scope,privacy,text,repo,project,entity,confidence,importance,
          created_at,updated_at,stale_after_days,source,metadata_json,evidence_json
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            memory["id"],
            memory["status"],
            memory["kind"],
            memory["scope"],
            memory["privacy"],
            memory["text"],
            memory.get("repo"),
            memory.get("project"),
            memory.get("entity"),
            float(memory.get("confidence", 0.6)),
            float(memory.get("importance", 0.5)),
            memory["created_at"],
            memory["updated_at"],
            memory.get("stale_after_days"),
            memory.get("source"),
            json.dumps(memory.get("metadata") or {}, sort_keys=True),
            json.dumps(memory.get("evidence") or [], sort_keys=True),
        ),
    )
    entities = set(memory.get("entities") or [])
    if memory.get("entity"):
        entities.add(str(memory["entity"]))
    for entity in sorted(e for e in entities if e):
        con.execute("INSERT INTO memory_entities(memory_id, entity) VALUES(?,?)", (memory["id"], entity))
    for ev in memory.get("evidence") or []:
        con.execute(
            "INSERT INTO memory_evidence(memory_id, kind, ref, note, created_at) VALUES(?,?,?,?,?)",
            (memory["id"], ev["kind"], ev["ref"], ev.get("note"), now),
        )
    after = {k: v for k, v in memory.items() if k != "entities"}
    revision(con, memory["id"], "insert", actor=actor, after=after, reason=reason)
    con.commit()
    append_jsonl(log_path(), {"ts": now, "action": "insert", "memory": after})
    return after


def cmd_write_candidate(args: argparse.Namespace) -> dict[str, Any]:
    evidence = parse_evidence(args.evidence or [])
    validate_common(args.kind, args.scope, args.privacy, args.text, evidence)
    con = connect()
    memory = insert_memory(
        con,
        {
            "id": sortable_id("memcand"),
            "status": "candidate",
            "kind": args.kind,
            "scope": args.scope,
            "privacy": args.privacy,
            "text": args.text,
            "repo": args.repo or None,
            "project": args.project or None,
            "entity": args.entity or None,
            "confidence": args.confidence,
            "importance": args.importance,
            "stale_after_days": args.stale_after_days,
            "source": args.source,
            "evidence": evidence,
            "metadata": json.loads(args.metadata_json or "{}"),
            "entities": args.entities or [],
        },
        actor=args.actor,
        reason=args.reason or "candidate created",
    )
    write_event("memory_candidate_created", {"memory_id": memory["id"], "kind": args.kind, "scope": args.scope})
    return command_result(True, memory=memory)


def get_memory(con: sqlite3.Connection, memory_id: str) -> dict[str, Any] | None:
    row = con.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
    return row_to_dict(row) if row else None


def cmd_promote(args: argparse.Namespace) -> dict[str, Any]:
    con = connect()
    current = get_memory(con, args.memory_id)
    if not current:
        raise ValueError(f"unknown memory: {args.memory_id}")
    evidence = list(current.get("evidence") or []) + parse_evidence(args.evidence or [])
    validate_common(current["kind"], current["scope"], current["privacy"], current["text"], evidence)
    if current["kind"] not in PREFERENCE_KINDS and not evidence:
        raise ValueError("promotion_requires_evidence")
    active = {**current, "id": sortable_id("mem"), "status": "active", "evidence": evidence}
    insert_memory(con, active, actor=args.actor, reason=args.reason or f"promoted from {args.memory_id}")
    before = current
    now = utc_now()
    metadata = current.get("metadata") or {}
    metadata["promoted_to"] = active["id"]
    con.execute(
        "UPDATE memories SET status=?, updated_at=?, metadata_json=? WHERE id=?",
        ("retired", now, json.dumps(metadata, sort_keys=True), args.memory_id),
    )
    revision(con, args.memory_id, "retire_after_promotion", actor=args.actor, before=before, after={**before, "status": "retired", "metadata": metadata}, reason=args.reason)
    con.commit()
    append_jsonl(log_path(), {"ts": now, "action": "promote", "from": args.memory_id, "to": active["id"]})
    write_event("memory_promoted", {"candidate_id": args.memory_id, "memory_id": active["id"], "kind": active["kind"], "scope": active["scope"]})
    return command_result(True, memory=active, retired_candidate=args.memory_id)


def cmd_query(args: argparse.Namespace) -> dict[str, Any]:
    con = connect()
    clauses: list[str] = []
    params: list[Any] = []
    if args.text:
        clauses.append("LOWER(text) LIKE ?")
        params.append(f"%{args.text.lower()}%")
    if args.kind:
        clauses.append("kind=?")
        params.append(args.kind)
    if args.scope:
        clauses.append("scope=?")
        params.append(args.scope)
    if args.repo:
        clauses.append("repo=?")
        params.append(args.repo)
    if args.entity:
        clauses.append("(entity=? OR id IN (SELECT memory_id FROM memory_entities WHERE entity=?))")
        params.extend([args.entity, args.entity])
    if args.status:
        clauses.append("status=?")
        params.append(args.status)
    elif not args.include_inactive:
        clauses.append("status IN ('active','candidate')")
    if args.confidence_min is not None:
        clauses.append("confidence>=?")
        params.append(args.confidence_min)
    if args.importance_min is not None:
        clauses.append("importance>=?")
        params.append(args.importance_min)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = con.execute(
        f"SELECT * FROM memories{where} ORDER BY importance DESC, confidence DESC, updated_at DESC LIMIT ?",
        (*params, args.limit),
    ).fetchall()
    memories = [row_to_dict(row) for row in rows]
    if args.redacted:
        for memory in memories:
            memory["text"] = redact_text(memory["text"])
    return command_result(True, count=len(memories), memories=memories, path=str(db_path()))


def cmd_status(args: argparse.Namespace) -> dict[str, Any]:
    action_map = {
        "retire": "retired",
        "stale": "stale",
        "contradict": "contradicted",
        "quarantine": "quarantined",
        "forget": "deleted",
    }
    target = action_map[args.action]
    con = connect()
    current = get_memory(con, args.memory_id)
    if not current:
        raise ValueError(f"unknown memory: {args.memory_id}")
    now = utc_now()
    text = "[deleted]" if target == "deleted" else current["text"]
    con.execute("UPDATE memories SET status=?, text=?, updated_at=? WHERE id=?", (target, text, now, args.memory_id))
    after = {**current, "status": target, "text": text, "updated_at": now}
    revision(con, args.memory_id, args.action, actor=args.actor, before=current, after=after, reason=args.reason)
    con.commit()
    append_jsonl(log_path(), {"ts": now, "action": args.action, "memory_id": args.memory_id, "status": target, "reason": args.reason})
    if target == "deleted":
        write_event("memory_forgotten", {"memory_id": args.memory_id})
    else:
        write_event("memory_retired", {"memory_id": args.memory_id, "status": target})
    return command_result(True, memory=after)


def cmd_export(args: argparse.Namespace) -> dict[str, Any]:
    con = connect()
    rows = con.execute("SELECT * FROM memories ORDER BY created_at ASC").fetchall()
    memories = [row_to_dict(row) for row in rows]
    if args.redacted:
        for memory in memories:
            memory["text"] = redact_text(memory["text"])
            if memory.get("privacy") in {"contains_pii", "local_only"}:
                memory["text"] = "[redacted]"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(json.dumps(m, sort_keys=True) for m in memories) + ("\n" if memories else ""), encoding="utf-8")
        return command_result(True, count=len(memories), output=str(out))
    return command_result(True, count=len(memories), memories=memories)


def cmd_import(args: argparse.Namespace) -> dict[str, Any]:
    imported = 0
    con = connect()
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        memory = json.loads(line)
        evidence = memory.get("evidence") or []
        validate_common(memory["kind"], memory["scope"], memory.get("privacy", "metadata"), memory["text"], evidence)
        if get_memory(con, memory["id"]):
            memory["id"] = sortable_id("memimp")
        insert_memory(con, memory, actor=args.actor, reason="imported")
        imported += 1
    return command_result(True, imported=imported)


def cmd_stats() -> dict[str, Any]:
    con = connect()
    rows = con.execute("SELECT kind, scope, status, source, COUNT(*) as n FROM memories GROUP BY kind, scope, status, source").fetchall()
    by_status: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_scope: dict[str, int] = {}
    for row in rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + row["n"]
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + row["n"]
        by_scope[row["scope"]] = by_scope.get(row["scope"], 0) + row["n"]
    total = sum(by_status.values())
    return command_result(True, path=str(db_path()), log_path=str(log_path()), total=total, by_status=by_status, by_kind=by_kind, by_scope=by_scope)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")

    w = sub.add_parser("write-candidate")
    w.add_argument("--kind", required=True, choices=sorted(KINDS))
    w.add_argument("--scope", required=True, choices=sorted(SCOPES))
    w.add_argument("--text", required=True)
    w.add_argument("--repo", default="")
    w.add_argument("--project", default="")
    w.add_argument("--entity", default="")
    w.add_argument("--entities", action="append", default=[])
    w.add_argument("--confidence", type=float, default=0.6)
    w.add_argument("--importance", type=float, default=0.5)
    w.add_argument("--privacy", choices=sorted(PRIVACY), default="metadata")
    w.add_argument("--source", default="manual")
    w.add_argument("--stale-after-days", type=int)
    w.add_argument("--metadata-json", default="{}")
    w.add_argument("--evidence", action="append", default=[])
    w.add_argument("--actor", default="cli")
    w.add_argument("--reason", default="")

    p = sub.add_parser("promote")
    p.add_argument("memory_id")
    p.add_argument("--evidence", action="append", default=[])
    p.add_argument("--actor", default="cli")
    p.add_argument("--reason", default="")

    q = sub.add_parser("query")
    q.add_argument("--text", default="")
    q.add_argument("--kind", choices=sorted(KINDS), default="")
    q.add_argument("--scope", choices=sorted(SCOPES), default="")
    q.add_argument("--entity", default="")
    q.add_argument("--repo", default="")
    q.add_argument("--status", choices=sorted(STATUSES), default="")
    q.add_argument("--confidence-min", type=float)
    q.add_argument("--importance-min", type=float)
    q.add_argument("--include-inactive", action="store_true")
    q.add_argument("--redacted", action="store_true")
    q.add_argument("--limit", type=int, default=50)

    s = sub.add_parser("status")
    s.add_argument("memory_id")
    s.add_argument("action", choices=["retire", "stale", "contradict", "quarantine", "forget"])
    s.add_argument("--actor", default="cli")
    s.add_argument("--reason", default="")

    f = sub.add_parser("forget")
    f.add_argument("memory_id")
    f.add_argument("--actor", default="cli")
    f.add_argument("--reason", default="forget requested")

    e = sub.add_parser("export")
    e.add_argument("--redacted", action="store_true")
    e.add_argument("--output", default="")

    im = sub.add_parser("import")
    im.add_argument("file")
    im.add_argument("--actor", default="cli")

    sub.add_parser("stats")
    sub.add_parser("path")

    args = parser.parse_args()
    try:
        if args.cmd == "init":
            connect().close()
            print_json(command_result(True, path=str(db_path()), log_path=str(log_path())))
        elif args.cmd == "write-candidate":
            print_json(cmd_write_candidate(args))
        elif args.cmd == "promote":
            print_json(cmd_promote(args))
        elif args.cmd == "query":
            print_json(cmd_query(args))
        elif args.cmd == "status":
            print_json(cmd_status(args))
        elif args.cmd == "forget":
            args.action = "forget"
            print_json(cmd_status(args))
        elif args.cmd == "export":
            print_json(cmd_export(args))
        elif args.cmd == "import":
            print_json(cmd_import(args))
        elif args.cmd == "stats":
            print_json(cmd_stats())
        elif args.cmd == "path":
            print(str(db_path()))
    except Exception as exc:
        print_json(command_result(False, error=str(exc)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
