#!/usr/bin/env python3
"""Stop hook: opt-in claim gate. Block if validation is claimed without ledger evidence."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2])).resolve()
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
    sys.exit(0)
if os.environ.get("ULTRAPROMPT_ENABLE_STOP_HOOK") != "1":
    sys.exit(0)

try:
    spec = importlib.util.spec_from_file_location("ultra_evidence_ledger", SCRIPTS_DIR / "evidence-ledger.py")
    ledger = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    assert spec and spec.loader
    spec.loader.exec_module(ledger)  # type: ignore[union-attr]
    from ultra_index import is_validation_command
except Exception:
    ledger = None  # type: ignore

try:
    payload = json.load(sys.stdin)
except Exception:
    payload = {}

try:
    if ledger is not None:
        ledger.append_event("Stop", payload if isinstance(payload, dict) else {"payload": payload})
except Exception:
    pass

transcript_text = ""
transcript_path = payload.get("transcript_path") if isinstance(payload, dict) else None
if transcript_path:
    p = Path(str(transcript_path)).expanduser()
    if p.exists() and p.is_file():
        try:
            transcript_text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            transcript_text = ""

claim_patterns = [
    r"\b(validation|tests?|lint|typecheck|build|checks?)\b[^\n]{0,80}\b(passed|green|succeeded|clean|successful)\b",
    r"\b(passed|green|succeeded|clean|successful)\b[^\n]{0,80}\b(validation|tests?|lint|typecheck|build|checks?)\b",
    r"\bI\s+ran\b[^\n]{0,80}\b(pytest|npm|pnpm|yarn|bun|go test|cargo|mvn|gradle|make|tsc|eslint|ruff|mypy|pyright)\b",
]
claims_validation = any(re.search(p, transcript_text, flags=re.I) for p in claim_patterns)

validation_seen = False
edits_seen = False
try:
    if ledger is not None:
        validation_seen = bool(ledger.has_validation_record())
        edits_seen = bool(ledger.has_edit_record())
except Exception:
    pass

if not validation_seen and transcript_text:
    try:
        validation_seen = any(
            is_validation_command(m.group(0))
            for m in re.finditer(
                r".{0,20}\b(pytest|npm|pnpm|yarn|bun|go\s+test|cargo|mvn|gradle|make|tsc|eslint|ruff|mypy|pyright|terraform\s+validate).{0,120}",
                transcript_text, flags=re.I,
            )
        )
    except Exception:
        validation_seen = False

if not edits_seen and transcript_text:
    edits_seen = bool(re.search(
        r'"(?:tool_name|name)"\s*:\s*"(?:Write|Edit|MultiEdit)"|\b(?:Write|Edit|MultiEdit)\b',
        transcript_text,
    ))

strict = os.environ.get("ULTRAPROMPT_STRICT_VALIDATION_GATE") == "1"
should_block = (claims_validation and not validation_seen) or (strict and edits_seen and not validation_seen)
if should_block:
    if strict and edits_seen and not claims_validation:
        reason = (
            "Ultraprompt strict validation gate: file edits were detected, but no validation command was found. "
            "Run a targeted validation command, or unset ULTRAPROMPT_STRICT_VALIDATION_GATE."
        )
    else:
        reason = (
            "Ultraprompt claim gate: validation appears to have been claimed, but no validation command was found "
            "in the evidence ledger or transcript. Run a targeted validation command and report the exact result, "
            "or call the claim_check MCP tool before claiming, or unset ULTRAPROMPT_ENABLE_STOP_HOOK."
        )
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
