#!/usr/bin/env python3
"""Shared V8 cognitive helpers for Ultraprompt."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = Path.home() / ".ultraprompt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def state_dir() -> Path:
    return Path(os.environ.get("ULTRAPROMPT_STATE_DIR") or os.environ.get("ULTRAPROMPT_STATE_DIR") or DEFAULT_STATE_DIR).expanduser()


def data_dir(name: str) -> Path:
    root = state_dir() / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def sortable_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{prefix}_{stamp}_{secrets.token_hex(3)}"


SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
]


def secret_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text or ""):
            findings.append(pattern.pattern)
    return findings


def pii_findings(text: str) -> list[str]:
    findings: list[str] = []
    for pattern in PII_PATTERNS:
        if pattern.search(text or ""):
            findings.append(pattern.pattern)
    return findings


def redact_text(text: str) -> str:
    out = text or ""
    for pattern in SECRET_PATTERNS:
        out = pattern.sub("[REDACTED_SECRET]", out)
    return out


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    if limit is not None:
        return rows[-limit:]
    return rows


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def stable_hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def plugin_version() -> str:
    for rel in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
        path = ROOT / rel
        if path.exists():
            try:
                version = json.loads(path.read_text(encoding="utf-8")).get("version")
                if version:
                    return str(version)
            except Exception:
                pass
    return "unknown"


def parse_kv_fields(values: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"field must be key=value: {value}")
        key, raw = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"empty key in field: {value}")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def command_result(ok: bool, **fields: Any) -> dict[str, Any]:
    return {
        "ok": ok,
        "schema_version": "ultraprompt.v8",
        "plugin_version": plugin_version(),
        **fields,
    }


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


class FileLock:
    def __init__(self, path: Path, stale_seconds: int = 3600):
        self.path = path
        self.stale_seconds = stale_seconds

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            age = time.time() - self.path.stat().st_mtime
            if age < self.stale_seconds:
                raise RuntimeError(f"lock already held: {self.path}")
            self.path.unlink(missing_ok=True)
        self.path.write_text(json.dumps({"pid": os.getpid(), "ts": utc_now()}), encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.path.unlink(missing_ok=True)
