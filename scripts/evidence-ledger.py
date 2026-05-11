#!/usr/bin/env python3
"""Record and report Ultraprompt evidence events.

Used as a Claude Code hook handler and as a local diagnostic. Best-effort:
hook recording must never interrupt normal work.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ultraprompt_index import is_validation_command  # noqa: E402

SENSITIVE_KEYS = {"stdout", "stderr", "output", "content", "text", "diff", "old_string", "new_string"}
EDIT_TOOLS = {"Write", "Edit", "MultiEdit"}


def plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".claude" / "plugins" / "data" / "ultraprompt"


def ledger_path() -> Path:
    override = os.environ.get("ULTRAPROMPT_LEDGER")
    if override:
        return Path(override).expanduser().resolve()
    return data_dir() / "evidence-ledger.jsonl"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def truncate(value: str, limit: int = 600) -> str:
    value = value.replace("\x00", "")
    return value if len(value) <= limit else value[: limit - 3] + "..."


def compact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "<truncated-depth>"
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            ks = str(key)
            if ks in SENSITIVE_KEYS:
                out[ks] = truncate(item) if isinstance(item, str) else f"<{type(item).__name__}>"
            else:
                out[ks] = compact(item, depth + 1)
        return out
    if isinstance(value, list):
        return [compact(item, depth + 1) for item in value[:20]]
    if isinstance(value, str):
        return truncate(value)
    return value


def extract_tool(payload: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    tool = str(payload.get("tool_name") or payload.get("tool") or payload.get("name") or "")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    tool_response = payload.get("tool_response") if isinstance(payload.get("tool_response"), dict) else {}
    if not tool and isinstance(payload.get("tool_use"), dict):
        tu = payload["tool_use"]
        tool = str(tu.get("name") or "")
        if isinstance(tu.get("input"), dict):
            tool_input = tu["input"]
    return tool, tool_input, tool_response


def summarize_payload(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    tool, tool_input, tool_response = extract_tool(payload)
    summary: dict[str, Any] = {"event": event}
    if payload.get("session_id"):
        summary["session_id"] = str(payload.get("session_id"))
    if payload.get("cwd"):
        summary["cwd"] = str(payload.get("cwd"))
    if payload.get("transcript_path"):
        summary["transcript_path"] = str(payload.get("transcript_path"))
    if tool:
        summary["tool"] = tool
    if tool == "Bash" or "command" in tool_input:
        command = str(tool_input.get("command", ""))
        summary["command"] = truncate(command, 1000)
        summary["validation_command"] = is_validation_command(command)
    if tool in EDIT_TOOLS:
        paths: list[str] = []
        for key in ("file_path", "path"):
            if isinstance(tool_input.get(key), str):
                paths.append(str(tool_input[key]))
        edits = tool_input.get("edits")
        if isinstance(edits, list):
            for e in edits:
                if isinstance(e, dict) and isinstance(e.get("file_path"), str):
                    paths.append(str(e["file_path"]))
        summary["edit_paths"] = sorted(set(paths))
    for key in ("exit_code", "status", "success", "error"):
        if key in tool_response:
            summary[key] = compact(tool_response[key])
    if event in {"SubagentStart", "SubagentStop"}:
        for key in ("agent_name", "subagent_name", "task", "description"):
            if key in payload:
                summary[key] = compact(payload.get(key))
    return summary


def append_event(event: str, payload: dict[str, Any]) -> None:
    try:
        path = ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        record = summarize_payload(event, payload)
        record["ts"] = now_iso()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, separators=(",", ":")) + "\n")
    except Exception:
        # Hooks must never block. Swallow.
        pass


def read_events() -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        pass
    return out


def has_validation_record() -> bool:
    return any(ev.get("validation_command") for ev in read_events())


def has_edit_record() -> bool:
    return any(ev.get("tool") in EDIT_TOOLS for ev in read_events())


def cmd_record(args: argparse.Namespace) -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            payload = {"payload": payload}
    except Exception:
        payload = {}
    append_event(args.event, payload)
    if not args.quiet:
        print(json.dumps({"event": args.event, "recorded": True}))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    events = read_events()
    if args.json:
        print(json.dumps({"path": str(ledger_path()), "count": len(events), "events": events}, indent=2))
        return 0
    print(f"Ledger: {ledger_path()}")
    print(f"Events: {len(events)}")
    by_event: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    validations = 0
    blocks = 0
    edits = 0
    for ev in events:
        by_event[ev.get("event", "?")] = by_event.get(ev.get("event", "?"), 0) + 1
        if ev.get("tool"):
            by_tool[ev["tool"]] = by_tool.get(ev["tool"], 0) + 1
        if ev.get("validation_command"):
            validations += 1
        if ev.get("event") == "hook-block":
            blocks += 1
        if ev.get("tool") in EDIT_TOOLS:
            edits += 1
    print(f"Validation commands: {validations}")
    print(f"Edit events: {edits}")
    print(f"Hook blocks: {blocks}")
    print("By event:")
    for k in sorted(by_event):
        print(f"  {k}: {by_event[k]}")
    if by_tool:
        print("By tool:")
        for k in sorted(by_tool):
            print(f"  {k}: {by_tool[k]}")
    return 0


def cmd_path(_args: argparse.Namespace) -> int:
    print(str(ledger_path()))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_rec = sub.add_parser("record")
    p_rec.add_argument("--event", required=True)
    p_rec.add_argument("--quiet", action="store_true")
    p_rec.set_defaults(func=cmd_record)
    p_rep = sub.add_parser("report")
    p_rep.add_argument("--json", action="store_true")
    p_rep.set_defaults(func=cmd_report)
    p_path = sub.add_parser("path")
    p_path.set_defaults(func=cmd_path)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
