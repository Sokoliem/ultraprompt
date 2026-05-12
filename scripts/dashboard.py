#!/usr/bin/env python3
"""Ultraprompt Dashboard (V8-track) — localhost catalog + telemetry UI.

Single-file aiohttp server. Endpoints:
  GET  /                          → dashboard/index.html
  GET  /assets/*                  → static files
  GET  /api/catalog               → full catalog tree
  GET  /api/catalog/<kind>/<name> → entity detail
  GET  /api/audit                 → catalog audit findings (cached 30s)
  GET  /api/router-bench          → last bench result (cached 5min)
  GET  /api/invocations           → paginated invocation history
  GET  /api/mission-state         → mission state snapshot
  GET  /api/stream                → SSE: live invocation events
  POST /api/validate              → validate artifact against schema

Usage:
  python3 scripts/dashboard.py [--port N] [--no-open]

State files:
  ~/.ultraprompt/state/dashboard.pid
  ~/.ultraprompt/state/dashboard.port
  ~/.ultraprompt/logs/dashboard.log
"""
from __future__ import annotations
import argparse
import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import logging
import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from aiohttp import web
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_DIR = ROOT / "dashboard"
ULTRAPROMPT_HOME = Path(os.environ.get("ULTRAPROMPT_STATE_DIR") or Path.home() / ".ultraprompt")
STATE_DIR = ULTRAPROMPT_HOME / "state"
LOG_DIR = ULTRAPROMPT_HOME / "logs"
EVIDENCE_DIR = ULTRAPROMPT_HOME / "evidence"
EVIDENCE_GRAPH_DIR = ULTRAPROMPT_HOME / "evidence-graph"
GAPS_DIR = ULTRAPROMPT_HOME / "gaps"
CLAUDE_LEDGER_DIR = Path.home() / ".claude" / "ultraprompt-data"
CODEX_LEDGER_DIR = Path.home() / ".codex" / "ultraprompt-data"
LEGACY_EVIDENCE_LEDGER = Path.home() / ".claude" / "plugins" / "data" / "ultraprompt" / "evidence-ledger.jsonl"

PID_FILE = STATE_DIR / "dashboard.pid"
PORT_FILE = STATE_DIR / "dashboard.port"
LOG_FILE = LOG_DIR / "dashboard.log"

for _dir in (STATE_DIR, LOG_DIR):
    try:
        _dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

_log_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
try:
    _log_handlers.insert(0, logging.FileHandler(LOG_FILE))
except OSError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_log_handlers,
)
log = logging.getLogger("dashboard")


# ─── Catalog loading ─────────────────────────────────────────────────────────

class Catalog:
    """In-memory catalog with mtime-based invalidation."""

    def __init__(self):
        self._cache: dict[str, Any] = {}
        self._mtimes: dict[str, float] = {}
        self._last_check = 0.0

    def _watch_paths(self) -> list[Path]:
        return [
            ROOT / "source" / "skill-specs.json",
            ROOT / "source" / "panel-specs.json",
            ROOT / "agents",
            ROOT / "commands",
            ROOT / "mcp" / "ultraprompt_meta.py",
        ]

    def _is_stale(self) -> bool:
        if not self._cache:
            return True
        if time.time() - self._last_check < 5:
            return False
        self._last_check = time.time()
        for p in self._watch_paths():
            if not p.exists():
                continue
            mtime = p.stat().st_mtime if p.is_file() else max(
                (f.stat().st_mtime for f in p.glob("*.md")), default=0
            )
            if mtime != self._mtimes.get(str(p)):
                self._mtimes[str(p)] = mtime
                return True
        return False

    def get(self) -> dict:
        if self._is_stale():
            self._rebuild()
        return self._cache

    def get_entity(self, kind: str, name: str) -> dict | None:
        cat = self.get()
        items = cat.get(kind, [])
        for item in items:
            if item.get("name") == name:
                return item
        return None

    def _rebuild(self):
        log.info("Rebuilding catalog cache")
        self._cache = {
            "version": self._plugin_version(),
            "agents": self._load_agents(),
            "skills": self._load_skills(),
            "commands": self._load_commands(),
            "panels": self._load_panels(),
            "mcp_tools": self._load_mcp_tools(),
            "artifact_schemas": self._load_artifact_schemas(),
            "stats": {},
        }
        c = self._cache
        c["stats"] = {
            "agents": len(c["agents"]),
            "skills": len(c["skills"]),
            "commands": len(c["commands"]),
            "panels": len(c["panels"]),
            "mcp_tools": len(c["mcp_tools"]),
            "artifact_schemas": len(c["artifact_schemas"]),
            "total_items": (len(c["agents"]) + len(c["skills"]) + len(c["commands"])
                            + len(c["panels"]) + len(c["mcp_tools"]) + len(c["artifact_schemas"])),
            "by_tier": {
                "core": sum(1 for s in c["skills"] if s.get("tier") == "core"),
                "specialist": sum(1 for s in c["skills"] if s.get("tier") == "specialist"),
                "ecosystem": sum(1 for s in c["skills"] if s.get("tier") == "ecosystem"),
            },
            "by_family": self._group_by_family(c["skills"]),
        }

    def _plugin_version(self) -> str:
        try:
            d = json.load(open(ROOT / ".claude-plugin" / "plugin.json"))
            return d.get("version", "unknown")
        except Exception:
            return "unknown"

    def _load_agents(self) -> list[dict]:
        out = []
        for p in sorted((ROOT / "agents").glob("*.md")):
            try:
                content = p.read_text()
                m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
                if not m:
                    continue
                fm = m.group(1)
                body = m.group(2)
                name = re.search(r"^name:\s*(.+)$", fm, re.MULTILINE)
                desc = re.search(r"^description:\s*(.+?)(?=\n[a-z_]+:|$)", fm, re.MULTILINE | re.DOTALL)
                color = re.search(r"^color:\s*(.+)$", fm, re.MULTILINE)
                tools = re.search(r"^tools:\s*(.+)$", fm, re.MULTILINE)
                out.append({
                    "name": name.group(1).strip() if name else p.stem,
                    "description": desc.group(1).strip() if desc else "",
                    "color": color.group(1).strip() if color else None,
                    "tools": [t.strip() for t in tools.group(1).split(",")] if tools else [],
                    "body": body,
                    "body_length": len(body),
                    "use_cases": self._extract_use_cases(desc.group(1) if desc else ""),
                    "lane_boundaries": self._extract_section(body, "Lane boundaries"),
                    "anti_patterns": self._extract_section(body, "Anti-patterns"),
                    "output_contract": self._extract_section(body, "Required output contract") or
                                       self._extract_section(body, "output contract"),
                    "path": str(p.relative_to(ROOT)),
                })
            except Exception as e:
                log.warning(f"Failed to parse {p}: {e}")
        return out

    def _load_skills(self) -> list[dict]:
        try:
            specs = json.load(open(ROOT / "source" / "skill-specs.json"))
            for s in specs:
                s["use_cases"] = self._extract_use_cases(s.get("description", ""))
                s["path"] = f"skills/{s['name']}/SKILL.md"
            return specs
        except Exception as e:
            log.warning(f"Failed to load skills: {e}")
            return []

    def _load_commands(self) -> list[dict]:
        out = []
        for p in sorted((ROOT / "commands").glob("*.md")):
            try:
                content = p.read_text()
                m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
                if m:
                    fm = m.group(1)
                    body = m.group(2)
                    desc = re.search(r"^description:\s*(.+?)(?=\n[a-z_]+:|$)", fm, re.MULTILINE | re.DOTALL)
                    arg = re.search(r"^argument-hint:\s*(.+)$", fm, re.MULTILINE)
                    out.append({
                        "name": p.stem,
                        "description": desc.group(1).strip() if desc else "",
                        "argument_hint": arg.group(1).strip() if arg else "",
                        "body": body,
                        "path": str(p.relative_to(ROOT)),
                    })
                else:
                    out.append({"name": p.stem, "description": "", "body": content, "path": str(p.relative_to(ROOT))})
            except Exception as e:
                log.warning(f"Failed to parse command {p}: {e}")
        return out

    def _load_panels(self) -> list[dict]:
        try:
            panels = json.load(open(ROOT / "source" / "panel-specs.json"))
            for p in panels:
                p["dispatch_count"] = sum(len(ph["agents"]) for ph in p.get("phases", []))
                p["phase_count"] = len(p.get("phases", []))
            return panels
        except Exception as e:
            log.warning(f"Failed to load panels: {e}")
            return []

    def _load_mcp_tools(self) -> list[dict]:
        try:
            env = os.environ.copy()
            env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
            result = subprocess.run(
                [sys.executable, str(ROOT / "mcp" / "ultraprompt_meta.py"), "--self-test"],
                capture_output=True, text=True, timeout=10, env=env,
            )
            data = json.loads(result.stdout)
            return data.get("result", {}).get("tools", [])
        except Exception as e:
            log.warning(f"Failed to load MCP tools: {e}")
            return []

    def _load_artifact_schemas(self) -> list[dict]:
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "artifact-validate.py"), "schemas"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(result.stdout)
            out = []
            for name in data.get("known_artifact_types", []):
                detail = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "artifact-validate.py"), "schema", name],
                    capture_output=True, text=True, timeout=10,
                )
                schema = json.loads(detail.stdout)
                out.append({
                    "name": name,
                    "schema": schema.get(name, {}),
                    "required": schema.get(name, {}).get("required", []),
                })
            return out
        except Exception as e:
            log.warning(f"Failed to load schemas: {e}")
            return []

    def _extract_use_cases(self, desc: str) -> list[str]:
        # Match 'USE WHEN ... \'phrase / phrase\'' regardless of trailing punctuation.
        patterns = [
            r"USE WHEN[^\'']*?\'(.+?)\'",
            r"when user says[^\'']*?\'(.+?)\'",
            r"USE WHEN user says\s*\'(.+?)\'",
        ]
        for pat in patterns:
            m = re.search(pat, desc, re.IGNORECASE | re.DOTALL)
            if m:
                phrases = re.split(r"\s*/\s*|\s*,\s*", m.group(1))
                return [p.strip() for p in phrases if p.strip()]
        return []

    def _extract_section(self, body: str, heading: str) -> str:
        pattern = rf"##\s*{re.escape(heading)}.*?\n(.*?)(?=\n##\s|\Z)"
        m = re.search(pattern, body, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    def _group_by_family(self, skills: list[dict]) -> dict:
        out = {}
        for s in skills:
            fam = s.get("family") or "uncategorized"
            out[fam] = out.get(fam, 0) + 1
        return out


# ─── Telemetry tailing ───────────────────────────────────────────────────────

class TelemetryTail:
    """Tail runtime ledgers and V8 cognitive JSONL streams."""

    def __init__(self):
        self._positions: dict[Path, int] = {}
        self._recent: list[dict] = []
        self._max_recent = 200
        self._subscribers: list[asyncio.Queue] = []
        self._primed = False

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    def recent(self, limit: int = 50) -> list[dict]:
        return self._recent[-limit:]

    def _record_type(self, rec: dict) -> str:
        return str(rec.get("type") or rec.get("event") or rec.get("kind") or "unknown")

    def _record_text(self, event: dict) -> str:
        try:
            return json.dumps(event, sort_keys=True, default=str).lower()
        except Exception:
            return str(event).lower()

    def _event_signal(self, event: dict) -> str:
        rec = event.get("record", {})
        event_type = self._record_type(rec)
        if event_type == "destructive_guard_classification" and rec.get("risk_class") == "LOW":
            return "noise"
        if event_type == "hook-block" and not any(rec.get(key) for key in ("reason", "tool", "command", "edit_paths")):
            return "noise"
        return "signal"

    def _matches_filters(self, event: dict, filters: dict[str, str]) -> bool:
        rec = event.get("record", {})
        event_type = self._record_type(rec)
        signal = self._event_signal(event)
        if filters.get("kind") and event.get("kind") != filters["kind"]:
            return False
        if filters.get("type") and event_type != filters["type"]:
            return False
        if filters.get("signal") in {"signal", "noise"} and signal != filters["signal"]:
            return False
        if filters.get("risk") and str(rec.get("risk_class") or "").lower() != filters["risk"].lower():
            return False
        if filters.get("source") and filters["source"] not in str(event.get("source", "")):
            return False
        if filters.get("q") and filters["q"].lower() not in self._record_text(event):
            return False
        return True

    def filtered_recent(self, limit: int = 50, filters: dict[str, str] | None = None) -> list[dict]:
        filters = filters or {}
        matches = [ev for ev in self._recent if self._matches_filters(ev, filters)]
        return matches[-limit:]

    def summary(self, events: list[dict] | None = None) -> dict:
        events = events if events is not None else list(self._recent)
        by_kind: dict[str, int] = {}
        by_type: dict[str, int] = {}
        by_signal = {"signal": 0, "noise": 0}
        guard_by_risk: dict[str, int] = {}
        top_guard_commands: dict[str, int] = {}
        for event in events:
            rec = event.get("record", {})
            kind = str(event.get("kind") or "unknown")
            event_type = self._record_type(rec)
            signal = self._event_signal(event)
            by_kind[kind] = by_kind.get(kind, 0) + 1
            by_type[event_type] = by_type.get(event_type, 0) + 1
            by_signal[signal] = by_signal.get(signal, 0) + 1
            if event_type == "destructive_guard_classification":
                risk = str(rec.get("risk_class") or "unknown")
                guard_by_risk[risk] = guard_by_risk.get(risk, 0) + 1
                command = str(rec.get("command_excerpt") or "").strip().split(" ", 1)[0] or "unknown"
                top_guard_commands[command] = top_guard_commands.get(command, 0) + 1
        total = len(events)
        noise_count = by_signal.get("noise", 0)
        low_guard = guard_by_risk.get("LOW", 0)
        guard_total = sum(guard_by_risk.values())
        if total == 0:
            verdict = "empty"
        elif noise_count / total >= 0.5:
            verdict = "noisy"
        elif guard_total and low_guard / guard_total >= 0.8:
            verdict = "guard-heavy"
        else:
            verdict = "signal"
        return {
            "total": total,
            "by_kind": dict(sorted(by_kind.items(), key=lambda item: (-item[1], item[0]))),
            "by_type": dict(sorted(by_type.items(), key=lambda item: (-item[1], item[0]))),
            "by_signal": by_signal,
            "guard_by_risk": dict(sorted(guard_by_risk.items(), key=lambda item: (-item[1], item[0]))),
            "top_guard_commands": dict(sorted(top_guard_commands.items(), key=lambda item: (-item[1], item[0]))[:12]),
            "noise_ratio": round(noise_count / total, 3) if total else 0,
            "low_guard_ratio": round(low_guard / guard_total, 3) if guard_total else 0,
            "verdict": verdict,
        }

    def source_status(self) -> list[dict]:
        out = []
        for path, kind in self._discover_sources().items():
            try:
                exists = path.exists()
                size = path.stat().st_size if exists else 0
            except OSError:
                exists = False
                size = 0
            out.append({
                "kind": kind,
                "path": str(path),
                "exists": exists,
                "size": size,
                "position": self._positions.get(path),
            })
        return out

    def _discover_sources(self) -> dict[Path, str]:
        sources: dict[Path, str] = {}

        def add(path: Path, kind: str) -> None:
            sources[path] = kind

        add(EVIDENCE_GRAPH_DIR / "nodes.jsonl", "evidence_graph_node")
        add(EVIDENCE_GRAPH_DIR / "edges.jsonl", "evidence_graph_edge")
        add(STATE_DIR / "mission-state-history.jsonl", "mission_state")
        add(ULTRAPROMPT_HOME / "events" / "events.jsonl", "cognitive_event")
        add(ULTRAPROMPT_HOME / "memory" / "memory.jsonl", "memory")
        add(ULTRAPROMPT_HOME / "learning" / "candidates.jsonl", "learning_candidate")
        add(LEGACY_EVIDENCE_LEDGER, "evidence_ledger")

        if EVIDENCE_DIR.exists():
            for path in sorted(EVIDENCE_DIR.glob("*.jsonl")):
                add(path, "evidence")

        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        for ledger_dir in (CLAUDE_LEDGER_DIR, CODEX_LEDGER_DIR):
            add(ledger_dir / f"events-{current_month}.jsonl", "ledger_v2")
            if ledger_dir.exists():
                for path in sorted(ledger_dir.glob("events-*.jsonl"))[-12:]:
                    add(path, "ledger_v2")

        return sources

    def _record_ts(self, rec: dict) -> int:
        ts = rec.get("ts")
        if isinstance(ts, (int, float)):
            return int(ts)
        if isinstance(ts, str):
            text = ts.strip()
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return int(parsed.timestamp())
            except ValueError:
                pass
        return int(time.time())

    def _emit_record(self, path: Path, kind: str, rec: dict, *, notify: bool) -> None:
        event = {
            "kind": kind,
            "source": path.name,
            "ts": self._record_ts(rec),
            "record": rec,
        }
        self._recent.append(event)
        if len(self._recent) > self._max_recent:
            self._recent = self._recent[-self._max_recent:]
        if not notify:
            return
        for sub in list(self._subscribers):
            try:
                sub.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def _parse_jsonl_lines(self, lines) -> list[dict]:
        records = []
        for line in lines:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="ignore")
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if isinstance(rec, dict):
                records.append(rec)
        return records

    def _prime_existing_file(self, path: Path, kind: str) -> None:
        if path in self._positions or not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for rec in self._parse_jsonl_lines(deque(f, maxlen=50)):
                    self._emit_record(path, kind, rec, notify=False)
            self._positions[path] = path.stat().st_size
        except OSError as e:
            log.debug(f"prime error {path}: {e}")

    def _read_new_records(self, path: Path, kind: str) -> None:
        stat = path.stat()
        pos = self._positions.get(path, 0)
        if pos > stat.st_size:
            pos = 0
        with open(path, "rb") as f:
            f.seek(pos)
            new_data = f.read()
            self._positions[path] = f.tell()
        if not new_data:
            return
        for rec in self._parse_jsonl_lines(new_data.decode("utf-8", errors="ignore").splitlines()):
            self._emit_record(path, kind, rec, notify=True)

    async def tail_loop(self):
        """Poll files every 500ms; emit new lines as events."""
        while True:
            try:
                sources = self._discover_sources()
                if not self._primed:
                    for path, kind in sources.items():
                        self._prime_existing_file(path, kind)
                    self._primed = True

                for path, kind in sources.items():
                    if not path.exists():
                        continue
                    try:
                        self._read_new_records(path, kind)
                    except Exception as e:
                        log.debug(f"tail error {path}: {e}")
            except Exception as e:
                log.warning(f"tail loop error: {e}")

            await asyncio.sleep(0.5)


# ─── Caching helpers ─────────────────────────────────────────────────────────

class TimedCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self._value = None
        self._stamp = 0.0

    def get(self):
        if self._value is None or time.time() - self._stamp > self.ttl:
            return None
        return self._value

    def set(self, v):
        self._value = v
        self._stamp = time.time()


# ─── HTTP handlers ───────────────────────────────────────────────────────────

catalog = Catalog()
telemetry = TelemetryTail()
audit_cache = TimedCache(30)
bench_cache = TimedCache(300)
mission_cache = TimedCache(5)


async def handle_index(request):
    return web.FileResponse(DASHBOARD_DIR / "index.html")


async def handle_static(request):
    rel = request.match_info["path"]
    p = DASHBOARD_DIR / rel
    if not p.exists() or not str(p.resolve()).startswith(str(DASHBOARD_DIR.resolve())):
        return web.Response(status=404)
    return web.FileResponse(p)


async def handle_catalog(request):
    return web.json_response(catalog.get())


async def handle_entity(request):
    kind = request.match_info["kind"]
    name = request.match_info["name"]
    entity = catalog.get_entity(kind, name)
    if not entity:
        return web.json_response({"error": "not found"}, status=404)
    # Augment with recent invocations
    recent = []
    for ev in reversed(telemetry.recent(200)):
        rec = ev.get("record", {})
        if name in json.dumps(rec):
            recent.append(ev)
        if len(recent) >= 10:
            break
    return web.json_response({**entity, "recent_invocations": recent})


async def handle_audit(request):
    cached = audit_cache.get()
    if cached is not None:
        return web.json_response(cached)
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "catalog-audit.py")],
            capture_output=True, text=True, timeout=30,
        )
        report_path = ROOT / "dist" / "catalog-audit-report.json"
        if report_path.exists():
            data = json.loads(report_path.read_text())
            audit_cache.set(data)
            return web.json_response(data)
        return web.json_response({"error": "audit ran but no report file"}, status=500)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_router_bench(request):
    cached = bench_cache.get()
    if cached is not None:
        return web.json_response(cached)
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run-router-bench.py")],
            capture_output=True, text=True, timeout=60,
        )
        # Parse text output into structured form
        text = result.stdout
        positive = re.search(r"top-1: (\d+)/(\d+) \(([\d.]+)%", text)
        top3 = re.search(r"top-3: (\d+)/(\d+) \(([\d.]+)%", text)
        adversarial = re.search(r"rejected: (\d+)/(\d+) \(([\d.]+)%", text)
        misses_t1 = re.findall(r"T1 MISS\s+'(.+?)' expected=(\S+) got=\[(.*?)\]", text)
        misses_t3 = re.findall(r"T3 MISS\s+'(.+?)' expected=(\S+) got=\[(.*?)\]", text)
        data = {
            "positive": {
                "top_1": {"pass": int(positive.group(1)), "total": int(positive.group(2)), "pct": float(positive.group(3))} if positive else None,
                "top_3": {"pass": int(top3.group(1)), "total": int(top3.group(2)), "pct": float(top3.group(3))} if top3 else None,
            },
            "adversarial": {
                "rejected": {"pass": int(adversarial.group(1)), "total": int(adversarial.group(2)), "pct": float(adversarial.group(3))} if adversarial else None,
            },
            "misses": {
                "top_1": [{"intent": i, "expected": e, "got": g} for i, e, g in misses_t1],
                "top_3": [{"intent": i, "expected": e, "got": g} for i, e, g in misses_t3],
            },
            "raw": text,
        }
        bench_cache.set(data)
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_invocations(request):
    try:
        limit = min(max(int(request.query.get("limit", "50")), 1), 1000)
    except ValueError:
        limit = 50
    filters = {
        key: request.query.get(key, "").strip()
        for key in ("kind", "type", "signal", "risk", "source", "q")
        if request.query.get(key, "").strip()
    }
    invocations = telemetry.filtered_recent(limit, filters)
    payload = {
        "invocations": invocations,
        "total_recent": len(telemetry._recent),
        "returned": len(invocations),
        "filters": filters,
        "summary": telemetry.summary(invocations),
        "overall_summary": telemetry.summary(),
    }
    export_format = request.query.get("format", "json").lower()
    if export_format == "jsonl":
        body = "\n".join(json.dumps(ev, default=str) for ev in invocations)
        if body:
            body += "\n"
        return web.Response(
            text=body,
            content_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=ultraprompt-telemetry.jsonl"},
        )
    return web.json_response(payload)


def hook_coverage_summary() -> dict:
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit-hook-coverage.py"), "--json"],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        data["exit"] = result.returncode
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def handle_health(request):
    return web.json_response({
        "ok": True,
        "total_recent": len(telemetry._recent),
        "telemetry_summary": telemetry.summary(),
        "sources": telemetry.source_status(),
        "hook_coverage": hook_coverage_summary(),
    })


def run_json_script(script_name: str, args: list[str] | None = None, timeout: int = 30) -> dict:
    args = args or []
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script_name), *args],
            capture_output=True, text=True, timeout=timeout, cwd=ROOT,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            data = {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr}
        data.setdefault("exit", result.returncode)
        return data
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


async def handle_cognitive_health(request):
    graph = run_json_script("build-capability-graph.py", ["--json"], timeout=45)
    memory = run_json_script("memory-store.py", ["stats"])
    dreams = run_json_script("dream-runner.py", ["status"])
    learning = run_json_script("learning-queue.py", ["stats"])
    events = run_json_script("cognitive-event-log.py", ["stats"])
    pathfinder = run_json_script("run-pathfinder-tests.py", ["--json", "--no-telemetry"], timeout=90)
    return web.json_response({
        "ok": all(item.get("ok", False) for item in [graph, memory, dreams, learning, events, pathfinder]),
        "graph": {
            "ok": graph.get("ok", False),
            "summary": {
                "node_count": len((graph.get("graph") or {}).get("nodes", [])),
                "edge_count": len((graph.get("graph") or {}).get("edges", [])),
                "health": (graph.get("graph") or {}).get("health", {}),
                "source_hash": (graph.get("graph") or {}).get("source_hash"),
            },
        },
        "memory": memory,
        "dreams": dreams,
        "learning": learning,
        "events": events,
        "pathfinder": pathfinder,
    })


async def handle_memory_query(request):
    args = ["query", "--limit", request.query.get("limit", "50")]
    for key in ("text", "kind", "scope", "entity", "repo", "status"):
        value = request.query.get(key)
        if value:
            args.extend([f"--{key.replace('_', '-')}", value])
    if request.query.get("include_inactive") == "1":
        args.append("--include-inactive")
    return web.json_response(run_json_script("memory-store.py", args))


async def handle_dreams_status(request):
    return web.json_response(run_json_script("dream-runner.py", ["status"]))


async def handle_learning_candidates(request):
    args = ["list", "--limit", request.query.get("limit", "100")]
    if request.query.get("status"):
        args.extend(["--status", request.query["status"]])
    if request.query.get("kind"):
        args.extend(["--kind", request.query["kind"]])
    return web.json_response(run_json_script("learning-queue.py", args))


async def handle_pathfind_api(request):
    intent = request.query.get("intent", "")
    if not intent:
        return web.json_response({"ok": False, "error": "intent required"}, status=400)
    args = ["pathfind", "--intent", intent, "--budget", request.query.get("budget", "standard"), "--dry-run"]
    if request.query.get("repo"):
        args.extend(["--repo", request.query["repo"]])
    if request.query.get("telemetry") != "1":
        args.append("--no-telemetry")
    return web.json_response(run_json_script("pathfinder.py", args, timeout=60))


async def handle_graph_api(request):
    return web.json_response(run_json_script("build-capability-graph.py", ["--json"], timeout=45))


async def handle_mission_state(request):
    cached = mission_cache.get()
    if cached is not None:
        return web.json_response(cached)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "mission-state.py"),
                "snapshot",
                "--worktree",
                str(ROOT),
                "--fast",
            ],
            capture_output=True, text=True, timeout=30, cwd=ROOT,
        )
        data = json.loads(result.stdout)
        mission_cache.set(data)
        return web.json_response(data)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_gaps_api(request):
    args = ["list", "--limit", request.query.get("limit", "50")]
    for key in ("repo", "status", "severity", "fingerprint"):
        value = request.query.get(key)
        if value:
            args.extend([f"--{key}", value])
    if request.query.get("history") == "1":
        args.append("--history")
    return web.json_response(run_json_script("gap-ledger.py", args, timeout=30))


async def handle_panel_runs_api(request):
    args = ["list", "--limit", request.query.get("limit", "20")]
    for key in ("repo", "panel", "status"):
        value = request.query.get(key)
        if value:
            args.extend([f"--{key}", value])
    if request.query.get("history") == "1":
        args.append("--history")
    return web.json_response(run_json_script("panel-runs.py", args, timeout=30))


async def handle_release_scorecard_api(request):
    target = request.query.get("target", "source")
    return web.json_response(run_json_script("release-scorecard.py", ["--check", "--json", "--target", target], timeout=120))


async def handle_validate(request):
    try:
        payload = await request.json()
        artifact_type = payload.get("artifact_type")
        artifact = payload.get("artifact")
        if not artifact_type:
            return web.json_response({"error": "artifact_type required"}, status=400)
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(artifact, f)
            tmp = f.name
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "artifact-validate.py"),
             "validate", artifact_type, tmp],
            capture_output=True, text=True, timeout=15,
        )
        Path(tmp).unlink(missing_ok=True)
        return web.json_response(json.loads(result.stdout))
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_stream(request):
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)

    # Replay recent events
    for ev in telemetry.recent(50):
        await response.write(f"event: invocation\ndata: {json.dumps(ev)}\n\n".encode())

    q = telemetry.subscribe()
    try:
        last_ping = time.time()
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=10)
                await response.write(f"event: invocation\ndata: {json.dumps(event)}\n\n".encode())
            except asyncio.TimeoutError:
                pass
            # 15s heartbeat
            if time.time() - last_ping > 15:
                await response.write(b": ping\n\n")
                last_ping = time.time()
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        telemetry.unsubscribe(q)
    return response


# ─── Server lifecycle ────────────────────────────────────────────────────────

def find_free_port(start: int = 5174, end: int = 5199) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port in {start}-{end}")


def write_pid(port: int):
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))
        PORT_FILE.write_text(str(port))
    except OSError as exc:
        log.warning("Dashboard PID state unavailable: %s", exc)


def cleanup_pid():
    try:
        PID_FILE.unlink(missing_ok=True)
        PORT_FILE.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("Dashboard PID cleanup skipped: %s", exc)


def is_pid_running(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            exit_code = wintypes.DWORD()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=5)
        return
    os.kill(pid, signal.SIGTERM)


def is_dashboard_running() -> tuple[bool, int | None, int | None]:
    """Returns (running, pid, port)."""
    try:
        if not PID_FILE.exists() or not PORT_FILE.exists():
            return False, None, None
        pid = int(PID_FILE.read_text().strip())
        port = int(PORT_FILE.read_text().strip())
        if is_pid_running(pid):
            return True, pid, port
        cleanup_pid()
        return False, None, None
    except (OSError, ValueError):
        cleanup_pid()
        return False, None, None


def make_app() -> "web.Application":
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/assets/{path:.+}", handle_static)
    app.router.add_get("/api/catalog", handle_catalog)
    app.router.add_get("/api/catalog/{kind}/{name}", handle_entity)
    app.router.add_get("/api/audit", handle_audit)
    app.router.add_get("/api/router-bench", handle_router_bench)
    app.router.add_get("/api/invocations", handle_invocations)
    app.router.add_get("/api/health", handle_health)
    app.router.add_get("/api/cognitive/health", handle_cognitive_health)
    app.router.add_get("/api/memory/query", handle_memory_query)
    app.router.add_get("/api/dreams/status", handle_dreams_status)
    app.router.add_get("/api/learning/candidates", handle_learning_candidates)
    app.router.add_get("/api/pathfind", handle_pathfind_api)
    app.router.add_get("/api/graph", handle_graph_api)
    app.router.add_get("/api/mission-state", handle_mission_state)
    app.router.add_get("/api/gaps", handle_gaps_api)
    app.router.add_get("/api/panel-runs", handle_panel_runs_api)
    app.router.add_get("/api/release-scorecard", handle_release_scorecard_api)
    app.router.add_get("/api/stream", handle_stream)
    app.router.add_post("/api/validate", handle_validate)
    return app


async def start_telemetry(app):
    app["telemetry_task"] = asyncio.create_task(telemetry.tail_loop())


async def stop_telemetry(app):
    app["telemetry_task"].cancel()
    try:
        await app["telemetry_task"]
    except asyncio.CancelledError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--stop", action="store_true")
    args = ap.parse_args()

    if args.status:
        running, pid, port = is_dashboard_running()
        print(json.dumps({
            "running": running,
            "pid": pid,
            "port": port,
            "url": f"http://localhost:{port}/" if port else None,
            "log": str(LOG_FILE),
        }, indent=2))
        return 0

    if args.stop:
        running, pid, port = is_dashboard_running()
        if running:
            terminate_pid(pid)
            time.sleep(0.5)
            cleanup_pid()
            print(json.dumps({"ok": True, "stopped_pid": pid}))
        else:
            print(json.dumps({"ok": True, "note": "not running"}))
        return 0

    if not HAS_AIOHTTP:
        print("ERROR: aiohttp not installed. Install with:")
        print("  pip3 install --user aiohttp")
        print("Then retry: /ultraprompt:dashboard")
        return 1

    running, pid, port = is_dashboard_running()
    if running:
        print(json.dumps({"already_running": True, "pid": pid, "port": port,
                          "url": f"http://localhost:{port}/"}))
        if not args.no_open:
            _open_browser(port)
        return 0

    port = args.port or find_free_port()
    write_pid(port)

    def _shutdown(*_):
        cleanup_pid()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        app = make_app()
        app.on_startup.append(start_telemetry)
        app.on_cleanup.append(stop_telemetry)

        log.info(f"Starting Ultraprompt Dashboard on http://localhost:{port}/")
        log.info(f"Plugin root: {ROOT}")
        log.info(f"Log file: {LOG_FILE}")

        if not args.no_open:
            _open_browser(port)

        web.run_app(app, host="127.0.0.1", port=port, print=None,
                    handle_signals=False, access_log=None)
    finally:
        cleanup_pid()
    return 0


def _open_browser(port: int):
    url = f"http://localhost:{port}/"
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform == "win32":
            os.startfile(url)
    except Exception as e:
        log.warning(f"Failed to auto-open browser: {e}")


if __name__ == "__main__":
    sys.exit(main())
