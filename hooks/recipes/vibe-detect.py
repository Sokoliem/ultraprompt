#!/usr/bin/env python3
"""UserPromptSubmit hook: detect vibe-coding intent and emit a /ultraprompt:vibe directive.

Mirrors the structure of `user-prompt-route-suggest.py`. Three branches:

- **Vibe phrase match** -> emit a directive instructing the model to invoke
  `ultraprompt:vibe` Skill before answering. The directive carries the original
  intent inline.
- **Short open-ended prompt** (no imperative verb, < `route_suggest.min_tokens`
  tokens won't reach us — but still > `vibe.min_tokens`) -> same directive.
- **Anything else** -> stay silent. The route-suggest hook handles ambiguous
  routing for prompts with clearer intent.

Suppression: stay silent if the prompt is empty, already routed (`/`, `!`,
contains `ultraprompt:`), or matches an imperative coding verb (build, fix,
write, refactor, etc.) — those have an obvious downstream skill and don't need
a picker.

Honors `ULTRAPROMPT_DISABLE_HOOKS=1` and the `hooks.vibe_detect_enabled` /
`[vibe]` config flags. Fails open on any error.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
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


# High-signal vibe phrases. Conservative on purpose — we want low false-positive rate
# because this hook competes with the existing route-suggest hook.
_VIBE_PHRASES = [
    re.compile(r"\bvibe\s+(with\s+me|coding|mode|session)\b", re.IGNORECASE),
    re.compile(r"\bnot\s+sure\s+what\s+to\s+(build|do|work\s+on|tackle|make)\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+(should|could)\s+i\s+(build|make|do|tackle|work\s+on)\b", re.IGNORECASE),
    re.compile(r"\bhelp\s+me\s+(think|explore|brainstorm|figure\s+out\s+what)\b", re.IGNORECASE),
    re.compile(r"\bexplore\s+(options|ideas|directions|paths)\b", re.IGNORECASE),
    re.compile(r"\bkicking\s+around\s+(ideas|options|some\s+ideas)\b", re.IGNORECASE),
    re.compile(r"\bgive\s+me\s+(some\s+)?(options|directions|paths|ideas)\b", re.IGNORECASE),
    re.compile(r"\bshow\s+me\s+what\s+i\s+could\s+(build|do|make)\b", re.IGNORECASE),
    re.compile(r"\b(i\s+want\s+to|i'd\s+like\s+to)\s+(build|make)\s+something\b", re.IGNORECASE),
]

# Imperative coding verbs — if present, the user already has a direction. Stay silent.
_IMPERATIVE_VERBS = re.compile(
    r"\b("
    r"build|fix|write|add|create|implement|refactor|review|debug|test|deploy|ship|"
    r"audit|check|inspect|run|update|delete|remove|rename|migrate|"
    r"explain|describe|show\s+me\s+how"
    r")\b",
    re.IGNORECASE,
)

_TRIVIAL_PHRASES = ("hi", "hello", "thanks", "thank you", "ok", "okay", "yes", "no", "sure")
_OPT_OUT_HINT = " (disable via `ULTRAPROMPT_DISABLE_HOOKS=1`)"


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


def _has_vibe_phrase(prompt: str) -> str | None:
    """Return the matched phrase pattern source on hit; None otherwise."""
    for pat in _VIBE_PHRASES:
        m = pat.search(prompt)
        if m:
            return m.group(0)
    return None


def _is_short_open_ended(prompt: str, max_tokens: int) -> bool:
    """A short prompt with no imperative verb is plausibly vibe-coding intent."""
    tokens = prompt.split()
    if len(tokens) > max_tokens:
        return False
    if _IMPERATIVE_VERBS.search(prompt):
        return False
    # Require at least a question mark or a vibe-flavored noun to avoid firing on
    # short statements ("the build is broken" or "tests fail on main").
    return ("?" in prompt) or bool(re.search(r"\b(idea|direction|option|something)\b", prompt, re.IGNORECASE))


def _emit_vibe_directive(prompt: str, reason: str) -> None:
    inline = {"intent": prompt, "reason": reason}
    text = (
        "ultraprompt vibe routing: the prompt looks like vibe-coding intent "
        f"({reason}). **Before answering, invoke the `ultraprompt:vibe` Skill with "
        "the user's prompt as `$ARGUMENTS`.** It will dispatch the `vibe-curator` "
        "agent to generate 4–8 prompt-path options across 2–4 lanes, then run a "
        "two-stage `AskUserQuestion` picker (lane → path), then expand the chosen "
        f"seed into a full detailed prompt for you to review.{_OPT_OUT_HINT}\n\n"
        f"Inline intent (use directly; no need to re-derive):\n```json\n{json.dumps(inline)}\n```"
    )
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }
    print(json.dumps(payload))


def _telemetry(led, *, repo: str | None, prompt_len: int, reason: str) -> None:
    if not led:
        return
    try:
        led.write_event(
            "vibe_detect_triggered",
            repo=repo,
            prompt_chars=prompt_len,
            reason=reason,
            session_id=os.environ.get("CLAUDE_SESSION_ID") or f"unknown-{int(time.time())}",
            runtime="claude-code",
        )
    except Exception:
        return


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
    if cfg and not cfg.get(config, "hooks.vibe_detect_enabled", True):
        return 0

    min_tokens = int((cfg.get(config, "vibe.min_tokens", 4) if cfg else 4) or 4)
    max_short_tokens = int((cfg.get(config, "vibe.short_open_ended_max_tokens", 10) if cfg else 10) or 10)
    only_unrouted = bool(
        (cfg.get(config, "vibe.only_unrouted", True) if cfg else True)
    )

    if _is_trivial(prompt, min_tokens):
        return 0

    # Stay silent if the user already invoked an ultraprompt skill/slash command.
    if only_unrouted and ("ultraprompt:" in prompt or "/ultraprompt" in prompt):
        return 0

    reason: str | None = None
    matched = _has_vibe_phrase(prompt)
    if matched:
        reason = f"vibe phrase: '{matched.lower()}'"
    elif _is_short_open_ended(prompt, max_short_tokens):
        reason = f"short open-ended prompt (<{max_short_tokens} tokens, no imperative verb)"

    if not reason:
        return 0

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

    _telemetry(led, repo=repo_n, prompt_len=len(prompt), reason=reason)
    _emit_vibe_directive(prompt, reason)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
