#!/usr/bin/env python3
"""Append-only V8 cognitive event log.

The log is local-first, JSONL, traceable, and privacy-aware. It intentionally
does not replace legacy evidence ledgers; it provides the cognitive substrate
for memory, dreams, learning, pathfinding, and dashboard governance.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cognitive_common import (
    append_jsonl,
    command_result,
    data_dir,
    parse_kv_fields,
    pii_findings,
    print_json,
    read_jsonl,
    redact_text,
    secret_findings,
    sortable_id,
    utc_now,
)

EVENT_TYPES = {
    "route_attempt",
    "route_outcome",
    "dispatch_decision",
    "panel_lifecycle",
    "mcp_tool_call",
    "artifact_validation",
    "user_feedback",
    "memory_candidate_created",
    "memory_promoted",
    "memory_retired",
    "memory_forgotten",
    "dream_started",
    "dream_completed",
    "dream_failed",
    "learning_candidate_created",
    "learning_candidate_applied",
    "learning_candidate_reverted",
    "pathfinder_decision",
    "dashboard_action",
}


def event_path() -> Path:
    custom = os.environ.get("ULTRAPROMPT_EVENT_LOG") or os.environ.get("ULTRAPROMPT_EVENT_LOG")
    if custom:
        return Path(custom).expanduser()
    custom_dir = os.environ.get("ULTRAPROMPT_EVENT_DIR") or os.environ.get("ULTRAPROMPT_EVENT_DIR")
    if custom_dir:
        return Path(custom_dir).expanduser() / "events.jsonl"
    return data_dir("events") / "events.jsonl"


def redact_payload(data: dict[str, Any], include_content: bool) -> dict[str, Any]:
    if include_content:
        return data
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key in {"prompt", "text", "content", "body", "diff"}:
            out[key] = "[omitted]"
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


def write_event(event_type: str, data: dict[str, Any], *, trace_id: str = "", correlation_id: str = "", privacy: str = "metadata") -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"unknown event type: {event_type}")
    raw = json.dumps(data, sort_keys=True)
    secrets = secret_findings(raw)
    if secrets:
        raise ValueError("contains_secret_blocked")
    pii = pii_findings(raw)
    privacy_class = privacy
    if pii and privacy == "metadata":
        privacy_class = "contains_pii"
    include_content = privacy_class in {"full", "local_only_full"}
    record = {
        "schema": "event.v1",
        "id": sortable_id("evt"),
        "type": event_type,
        "ts": utc_now(),
        "trace_id": trace_id or sortable_id("trace"),
        "correlation_id": correlation_id or "",
        "privacy": privacy_class,
        "data": redact_payload(data, include_content=include_content),
    }
    append_jsonl(event_path(), record)
    return record


def parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def query_events(args: argparse.Namespace) -> list[dict[str, Any]]:
    rows = read_jsonl(event_path())
    cutoff = None
    if args.days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    out: list[dict[str, Any]] = []
    for row in rows:
        if args.type and row.get("type") != args.type:
            continue
        if args.trace_id and row.get("trace_id") != args.trace_id:
            continue
        if args.correlation_id and row.get("correlation_id") != args.correlation_id:
            continue
        if cutoff:
            ts = parse_ts(str(row.get("ts", "")))
            if ts and ts < cutoff:
                continue
        if not args.include_content:
            row = {**row, "data": redact_payload(row.get("data", {}), include_content=False)}
        out.append(row)
    return out[-args.limit :]


def stats() -> dict[str, Any]:
    rows = read_jsonl(event_path())
    by_type: dict[str, int] = {}
    by_privacy: dict[str, int] = {}
    for row in rows:
        by_type[str(row.get("type", "unknown"))] = by_type.get(str(row.get("type", "unknown")), 0) + 1
        by_privacy[str(row.get("privacy", "unknown"))] = by_privacy.get(str(row.get("privacy", "unknown")), 0) + 1
    return command_result(True, path=str(event_path()), total=len(rows), by_type=by_type, by_privacy=by_privacy)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    write = sub.add_parser("write")
    write.add_argument("type", choices=sorted(EVENT_TYPES))
    write.add_argument("--field", action="append", default=[], help="key=value field, JSON values accepted")
    write.add_argument("--json", dest="json_payload", default="", help="JSON object payload")
    write.add_argument("--trace-id", default="")
    write.add_argument("--correlation-id", default="")
    write.add_argument("--privacy", choices=["metadata", "full", "local_only_full"], default="metadata")

    query = sub.add_parser("query")
    query.add_argument("--type", choices=sorted(EVENT_TYPES), default="")
    query.add_argument("--trace-id", default="")
    query.add_argument("--correlation-id", default="")
    query.add_argument("--days", type=int, default=30)
    query.add_argument("--limit", type=int, default=50)
    query.add_argument("--include-content", action="store_true")

    sub.add_parser("stats")
    sub.add_parser("path")

    args = parser.parse_args()
    try:
        if args.cmd == "write":
            payload = parse_kv_fields(args.field)
            if args.json_payload:
                parsed = json.loads(args.json_payload)
                if not isinstance(parsed, dict):
                    raise ValueError("--json must be an object")
                payload.update(parsed)
            print_json(command_result(True, event=write_event(args.type, payload, trace_id=args.trace_id, correlation_id=args.correlation_id, privacy=args.privacy)))
        elif args.cmd == "query":
            events = query_events(args)
            print_json(command_result(True, count=len(events), events=events, path=str(event_path())))
        elif args.cmd == "stats":
            print_json(stats())
        elif args.cmd == "path":
            print(str(event_path()))
    except Exception as exc:
        print_json(command_result(False, error=str(exc)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
