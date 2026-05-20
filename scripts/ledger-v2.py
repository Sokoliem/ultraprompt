#!/usr/bin/env python3
"""V8 always-on ledger v2. Append-only JSONL, monthly rotation.

Writes to the active runtime ledger and reads across Claude Code + Codex
ledgers so dashboard and doctor commands see both clients.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


@lru_cache(maxsize=1)
def process_runtime_hint() -> str:
    """Infer runtime from the process tree when the host does not export env hints."""
    if os.name != "posix":
        return ""
    try:
        pid = os.getppid()
        for _ in range(8):
            if pid <= 1:
                break
            command = subprocess.check_output(
                ["ps", "-o", "comm=", "-p", str(pid)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            lowered = command.lower()
            base = Path(command).name.lower()
            if "codex.app" in lowered or base == "codex":
                return "codex"
            if base in {"claude", "claude-code"} or "claude code.app" in lowered:
                return "claude-code"
            parent = subprocess.check_output(
                ["ps", "-o", "ppid=", "-p", str(pid)],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
            if not parent:
                break
            pid = int(parent)
    except Exception:
        return ""
    return ""


def recent_codex_session_id() -> str:
    """Best-effort session id for Codex Desktop/CLI runs that do not export CODEX_SESSION_ID."""
    try:
        root = Path.home() / ".codex" / "sessions"
        if not root.exists():
            return ""
        now = time.time()
        cwd = Path.cwd().resolve()
        newest_id = ""
        for path in sorted(root.glob("**/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:25]:
            if now - path.stat().st_mtime > 12 * 3600:
                continue
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                first = f.readline()
            event = json.loads(first)
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            if "codex" not in str(payload.get("originator", "")).lower():
                continue
            sid = str(payload.get("id") or "")
            if not newest_id and sid:
                newest_id = sid
            session_cwd = payload.get("cwd")
            if session_cwd and Path(str(session_cwd)).expanduser().resolve() == cwd and sid:
                return sid
        return newest_id
    except Exception:
        return ""


def runtime_name() -> str:
    """Return the active client runtime for telemetry normalization."""
    if any(os.environ.get(name) for name in ("CODEX_SESSION_ID", "CODEX_VERSION", "CODEX_HOME")):
        return "codex"
    if any(os.environ.get(name) for name in ("CLAUDE_SESSION_ID", "CLAUDECODE", "CLAUDE_PLUGIN_ROOT")):
        return "claude-code"
    hint = process_runtime_hint()
    if hint:
        return hint
    return "unknown"


def session_id() -> str:
    for name in ("CODEX_SESSION_ID", "CLAUDE_SESSION_ID", "ULTRAPROMPT_SESSION_ID"):
        value = os.environ.get(name)
        if value:
            return value
    if runtime_name() == "codex":
        inferred = recent_codex_session_id()
        if inferred:
            return inferred
    return f"unknown-{int(time.time())}"


def plugin_version() -> str:
    root = Path(__file__).resolve().parents[1]
    for rel in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        try:
            data = json.loads((root / rel).read_text(encoding="utf-8"))
            version = data.get("version")
            if version:
                return str(version)
        except Exception:
            continue
    return "unknown"


def repo_context() -> tuple[str, str]:
    try:
        worktree = Path.cwd().resolve()
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=worktree,
            capture_output=True,
            text=True,
            timeout=3,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            root = Path(proc.stdout.strip()).resolve()
            return root.name, str(root)
        return worktree.name, str(worktree)
    except Exception:
        cwd = Path.cwd().resolve()
        return cwd.name, str(cwd)


def _runtime_home_name() -> str:
    if runtime_name() == "codex":
        return ".codex"
    return ".claude"


def _ledger_dir_for(home_name: str) -> Path:
    return Path.home() / home_name / "ultraprompt-data"


def active_ledger_dir() -> Path:
    override = os.environ.get("ULTRAPROMPT_LEDGER_DIR")
    if override:
        return Path(override).expanduser()
    return _ledger_dir_for(_runtime_home_name())


def ledger_dirs() -> list[Path]:
    paths = [active_ledger_dir(), _ledger_dir_for(".claude"), _ledger_dir_for(".codex")]
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        out.append(resolved)
    return out


LEDGER_DIR = active_ledger_dir()
LEDGER_DIR.mkdir(parents=True, exist_ok=True)


def current_ledger_path() -> Path:
    return LEDGER_DIR / f"events-{datetime.now(timezone.utc).strftime('%Y-%m')}.jsonl"


def write_event(event_type: str, **fields: Any) -> None:
    try:
        repo, worktree = repo_context()
        event = {
            "v": SCHEMA_VERSION,
            "ts": int(time.time()),
            "type": event_type,
            "runtime": runtime_name(),
            "session_id": session_id(),
            "plugin_version": plugin_version(),
            "source": fields.pop("source", "ledger-v2"),
            "repo": fields.pop("repo", repo),
            "worktree": fields.pop("worktree", worktree),
            **fields,
        }
        with open(current_ledger_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
    except Exception:
        if os.environ.get("ULTRAPROMPT_DEBUG"):
            import traceback; traceback.print_exc(file=sys.stderr)


def read_events(days=30, event_types=None, repo=None, worktree=None) -> list[dict]:
    cutoff = time.time() - days * 86400
    events = []
    months_back = max(1, days // 28 + 2)
    seen = set()
    for ledger_dir in ledger_dirs():
        for i in range(months_back):
            d = datetime.now(timezone.utc) - timedelta(days=i * 28)
            path = ledger_dir / f"events-{d.strftime('%Y-%m')}.jsonl"
            if path in seen or not path.exists():
                continue
            seen.add(path)
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if e.get("ts", 0) < cutoff:
                        continue
                    if event_types and e.get("type") not in event_types:
                        continue
                    if repo and e.get("repo") != repo:
                        continue
                    if worktree and e.get("worktree") != worktree:
                        continue
                    events.append(e)
            except OSError:
                continue
    events.sort(key=lambda x: x.get("ts", 0))
    return events


def prune(retention_days=365) -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    removed = 0
    for ledger_dir in ledger_dirs():
        if not ledger_dir.exists():
            continue
        for path in ledger_dir.glob("events-*.jsonl"):
            m = re.match(r"events-(\d{4})-(\d{2})\.jsonl$", path.name)
            if not m:
                continue
            if datetime(int(m.group(1)), int(m.group(2)), 1) < cutoff:
                path.unlink()
                removed += 1
    return removed


def summary(days=7) -> dict:
    events = read_events(days=days)
    by_type, skills, mcp, repos = {}, {}, {}, {}
    wips = claims = sessions = 0
    for e in events:
        t = e.get("type", "")
        by_type[t] = by_type.get(t, 0) + 1
        if t == "skill_invocation":
            skills[e.get("skill", "?")] = skills.get(e.get("skill", "?"), 0) + 1
        elif t == "mcp_tool_call":
            mcp[e.get("tool", "?")] = mcp.get(e.get("tool", "?"), 0) + 1
        elif t == "wip_save":
            wips += 1
        elif t == "claim_flagged":
            claims += 1
        elif t == "session_start":
            sessions += 1
        if e.get("repo"):
            repos[e["repo"]] = repos.get(e["repo"], 0) + 1
    return {"window_days": days, "total_events": len(events), "by_type": by_type,
            "top_skills": dict(sorted(skills.items(), key=lambda x: -x[1])[:10]),
            "top_mcp_tools": dict(sorted(mcp.items(), key=lambda x: -x[1])[:10]),
            "top_repos": dict(sorted(repos.items(), key=lambda x: -x[1])[:10]),
            "wip_saves": wips, "claims_flagged": claims, "sessions": sessions}


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("path")
    sub.add_parser("prune")
    s = sub.add_parser("summary"); s.add_argument("--days", type=int, default=7)
    s = sub.add_parser("query")
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--type", action="append", default=None)
    s.add_argument("--repo", default=None); s.add_argument("--worktree", default=None)
    s = sub.add_parser("write"); s.add_argument("type"); s.add_argument("--field", action="append", default=[])
    args = p.parse_args()
    if args.cmd == "path":
        print(current_ledger_path())
    elif args.cmd == "prune":
        print(f"Pruned {prune()} ledger file(s).")
    elif args.cmd == "summary":
        print(json.dumps(summary(args.days), indent=2))
    elif args.cmd == "query":
        for e in read_events(args.days, args.type, args.repo, args.worktree):
            print(json.dumps(e))
    elif args.cmd == "write":
        fields = {}
        for f in args.field:
            if "=" in f:
                k, v = f.split("=", 1); fields[k] = v
        write_event(args.type, **fields); print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
