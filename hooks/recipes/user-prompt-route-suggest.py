#!/usr/bin/env python3
"""V8.7 UserPromptSubmit hook: routing nudge + interactive picker.

When the user submits a prompt, score it against the V8 skill index. Three
branches:

- **High-confidence + clear winner** -> emit the existing single-line passive
  nudge ("this matches /ultraprompt:<skill>").
- **Ambiguous** (top-2 within `ambiguity_gap`, OR top is `medium` confidence)
  -> emit a *directive* instructing the model to invoke `ultraprompt:choose`
  before answering. The directive carries the top-N candidates inline so the
  picker skill can build its `AskUserQuestion` panel without rescoring.
- **Trivial / low / already-routed** -> stay silent.

The hook never blocks; it fails open on any error. Respects
`ULTRAPROMPT_DISABLE_HOOKS=1` and config flags under `[hooks]` /
`[route_suggest]` in `source/config-defaults.toml`.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def _imp(name: str, path: Path):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


_HIGH_CONF_TRIGGERED = ("high",)
_TRIVIAL_PHRASES = ("hi", "hello", "thanks", "thank you", "ok", "okay", "yes", "no", "sure")


def _is_trivial(prompt: str, min_tokens: int) -> bool:
    stripped = prompt.strip()
    if not stripped:
        return True
    if stripped.startswith("/") or stripped.startswith("!"):
        return True
    low = stripped.lower()
    if low in _TRIVIAL_PHRASES:
        return True
    return len(stripped.split()) < min_tokens


def _emit_nudge(skill: str, confidence: str, why: str) -> None:
    cmd = f"/ultraprompt:{skill}"
    text = (
        f"ultraprompt routing suggestion ({confidence}): this prompt matches `{cmd}`. "
        "Invoke via the Skill tool (or run the slash command) unless you have a clear reason "
        "to handle it inline. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the "
        "dispatch decision tree."
    )
    if why:
        text += f"\nWhy: {why}"
    _print_additional_context(text)


def _emit_picker_directive(prompt: str, candidates: list[dict], gap: float, reason: str) -> None:
    """Emit a directive instructing the model to invoke `ultraprompt:choose`.

    Carries the top candidates inline so the picker skill can build its
    AskUserQuestion panel without rescoring.
    """
    top_cmds = ", ".join(f"`/ultraprompt:{c['skill']}`" for c in candidates[:3])
    inline = {
        "intent": prompt,
        "reason": reason,
        "gap": round(gap, 3),
        "candidates": [
            {
                "skill": c.get("skill"),
                "command": c.get("command") or f"/ultraprompt:{c.get('skill')}",
                "confidence": c.get("confidence"),
                "score": c.get("score"),
                "why": c.get("why"),
            }
            for c in candidates[:3]
        ],
    }
    text = (
        f"ultraprompt routing: this prompt matches multiple skills ({reason} - {top_cmds}). "
        "**Before answering, invoke the `ultraprompt:choose` Skill with the user's prompt as "
        "`$ARGUMENTS`.** It will present an interactive picker (AskUserQuestion) with previews "
        "and 2 LLM-rewritten prompt variants paired with their best-matching skills, then "
        "dispatch to the chosen skill.\n\n"
        f"Inline candidates (use these directly; do not re-score):\n```json\n{json.dumps(inline)}\n```"
    )
    _print_additional_context(text)


def _print_additional_context(text: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }
    print(json.dumps(payload))


def _telemetry_suggest(led, *, repo: str | None, prompt_len: int, top: dict | None, suggested: bool) -> None:
    if not led:
        return
    try:
        led.write_event(
            "route_suggest",
            repo=repo,
            prompt_chars=prompt_len,
            top_skill=(top or {}).get("skill"),
            top_confidence=(top or {}).get("confidence"),
            top_score=(top or {}).get("score"),
            suggested=suggested,
            session_id=os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}",
            runtime="claude-code",
        )
    except Exception:
        return


def _telemetry_picker(led, *, repo: str | None, prompt_len: int, top: dict | None, gap: float, reason: str) -> None:
    if not led:
        return
    try:
        led.write_event(
            "route_picker_triggered",
            repo=repo,
            prompt_chars=prompt_len,
            top_skill=(top or {}).get("skill"),
            top_confidence=(top or {}).get("confidence"),
            top_score=(top or {}).get("score"),
            gap=round(gap, 3),
            reason=reason,
            session_id=os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}",
            runtime="claude-code",
        )
    except Exception:
        return


def _compute_gap(top: list[dict]) -> float:
    """Relative gap between top-1 and top-2 scores; 1.0 if only one candidate."""
    if len(top) < 2:
        return 1.0
    s1 = float(top[0].get("score") or 0.0)
    s2 = float(top[1].get("score") or 0.0)
    if s1 <= 0:
        return 1.0
    return max(0.0, (s1 - s2) / s1)


def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    prompt = str(payload.get("prompt") or "")
    if not prompt:
        return 0

    cfg = _imp("cfg", PR / "scripts" / "config-loader.py")
    config = cfg.load_config() if cfg else {}
    if cfg and not cfg.get(config, "hooks.route_suggest_enabled", True):
        return 0

    min_tokens = int((cfg.get(config, "route_suggest.min_tokens", 4) if cfg else 4) or 4)
    score_threshold = float(
        (cfg.get(config, "route_suggest.min_score", 18.0) if cfg else 18.0) or 18.0
    )
    accept_medium = bool(
        (cfg.get(config, "route_suggest.accept_medium", False) if cfg else False) or False
    )
    only_unrouted = bool(
        (cfg.get(config, "route_suggest.only_unrouted", True) if cfg else True)
    )
    picker_enabled = bool(
        (cfg.get(config, "route_suggest.picker_enabled", True) if cfg else True)
    )
    ambiguity_gap = float(
        (cfg.get(config, "route_suggest.ambiguity_gap", 0.15) if cfg else 0.15) or 0.15
    )
    ambiguity_medium_conf = bool(
        (cfg.get(config, "route_suggest.ambiguity_medium_confidence", True) if cfg else True)
    )

    if _is_trivial(prompt, min_tokens):
        return 0

    # If the user already invoked an ultraprompt skill or slash command, stay silent.
    if only_unrouted and ("ultraprompt:" in prompt or "/ultraprompt" in prompt):
        return 0

    sys.path.insert(0, str(PR / "scripts"))
    try:
        from ultraprompt_index import build_index, find_plugin_root, route_intent  # type: ignore
    except Exception:
        return 0

    try:
        root = find_plugin_root(PR)
        index = build_index(root)
        top = route_intent(index, prompt, limit=3)
    except Exception:
        return 0

    if not top:
        return 0

    best = top[0]
    confidence = str(best.get("confidence", "low"))
    score = float(best.get("score") or 0.0)
    gap = _compute_gap(top)

    led = _imp("led", PR / "scripts" / "ledger-v2.py")
    ws = _imp("ws", PR / "scripts" / "worktree-state.py")
    repo_n = None
    if ws:
        try:
            root_path = ws.find_repo_root(Path.cwd().resolve())
            if root_path:
                repo_n = ws.repo_name(root_path)
        except Exception:
            pass

    # Ambiguity branch (V8.7): two near-equal candidates OR medium-confidence top match.
    # Manual-only skills are allowed in the picker — the picker skill instructs the
    # user to run the slash command directly when the chosen skill is manual_only.
    ambiguous_reason = ""
    if picker_enabled and score >= score_threshold:
        if len(top) >= 2 and gap < ambiguity_gap:
            ambiguous_reason = f"top-2 within {gap:.0%}"
        elif ambiguity_medium_conf and confidence == "medium":
            ambiguous_reason = "top match medium confidence"

    if ambiguous_reason:
        _telemetry_picker(led, repo=repo_n, prompt_len=len(prompt), top=best, gap=gap, reason=ambiguous_reason)
        _emit_picker_directive(prompt, top, gap, ambiguous_reason)
        return 0

    # High-confidence nudge branch (unchanged from V8.6).
    suggested = False
    if confidence in _HIGH_CONF_TRIGGERED and score >= score_threshold:
        suggested = True
    elif accept_medium and confidence == "medium" and score >= score_threshold:
        suggested = True

    _telemetry_suggest(led, repo=repo_n, prompt_len=len(prompt), top=best, suggested=suggested)

    if not suggested:
        return 0
    if bool(best.get("manual_only")):
        return 0

    _emit_nudge(best["skill"], confidence, str(best.get("why") or ""))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
