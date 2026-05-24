#!/usr/bin/env python3
"""V8 Stop hook: auto-WIP-save on dirty growth."""
from __future__ import annotations
import importlib.util, json, os, subprocess, sys, time
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return m
    except Exception:
        return None


def main():
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1": return 0
    try: sys.stdin.read()
    except Exception: pass
    cfg = _imp("cfg", PR / "scripts" / "config-loader.py")
    ws = _imp("ws", PR / "scripts" / "worktree-state.py")
    led = _imp("ledger_v2", PR / "scripts" / "ledger-v2.py")
    if not (cfg and ws): return 0
    config = cfg.load_config()
    if not cfg.get(config, "auto_wip_save.enabled", True): return 0
    if not cfg.get(config, "hooks.auto_wip_save_enabled", True): return 0
    if ws.find_repo_root() is None: return 0
    cwd = Path.cwd().resolve()
    state = ws.worktree_state(cwd)
    if state.get("in_progress"): return 0
    dirty = state.get("dirty_count", 0) + state.get("untracked_count", 0)
    threshold = cfg.get(config, "auto_wip_save.delta_threshold", 10)
    cool = cfg.get(config, "auto_wip_save.cooldown_minutes", 15)
    if dirty < threshold: return 0
    if led and cfg.get(config, "ledger.enabled", True):
        try:
            recent = led.read_events(days=1, event_types=["wip_save"], worktree=str(cwd))
            if recent and time.time() - max(e.get("ts", 0) for e in recent) < cool * 60:
                return 0
        except Exception: pass
    timeout_seconds = cfg.get(config, "auto_wip_save.timeout_seconds", 30)

    def _run(extra_args=()):
        return subprocess.run(
            [sys.executable, str(PR / "scripts" / "wip-save.py"),
             "--worktree", str(cwd), "--trigger", "hook-stop", *extra_args],
            capture_output=True, text=True, timeout=timeout_seconds,
        )

    try:
        r = _run()  # V8 verified-snapshot path
        if r.returncode != 0:
            # V8 failed — retry with --legacy fallback (PRD §8.1 safety net)
            r = _run(["--legacy"])
        if r.returncode == 0:
            try:
                sr = json.loads(r.stdout)
                if sr.get("ok") and sr.get("branch_created"):
                    impl = sr.get("implementation", "verified")
                    badge = "verified" if impl == "verified" else "legacy-fallback"
                    print(json.dumps({"systemMessage": f"ultraprompt: auto-saved {sr.get('files_saved', dirty)} dirty files to {sr['branch_created']} ({badge})"}))
            except json.JSONDecodeError: pass
    except subprocess.TimeoutExpired:
        # V8.8 (PRD S3 / §9.5): record hook-timeout event + surface a stderr warning so
        # the user knows their work was NOT auto-saved.
        if led and cfg.get(config, "ledger.enabled", True):
            try:
                led.write_event(
                    "hook-timeout",
                    hook="auto-wip-save",
                    duration_ms=int(timeout_seconds * 1000),
                    bypass_active=os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1",
                )
            except Exception:
                pass
        print(
            f"[Ultraprompt auto-wip-save] Timed out after {timeout_seconds}s. "
            "Your changes are NOT saved. Run /ultraprompt:wip-save manually.",
            file=sys.stderr,
        )
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    try: sys.exit(main())
    except Exception: sys.exit(0)
