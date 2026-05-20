#!/usr/bin/env python3
"""V8 launchd-driven worktree monitor."""
from __future__ import annotations
import argparse, importlib.util, json, os, subprocess, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))


def _imp(n, p):
    try:
        spec = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m); return m
    except Exception:
        return None


def in_quiet_hours(config):
    cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")
    if cfg is None: return False
    s = cfg.get(config, "notification.quiet_hours_start", "22:00")
    e = cfg.get(config, "notification.quiet_hours_end", "08:00")
    try:
        sh, sm = map(int, s.split(":")); eh, em = map(int, e.split(":"))
        n = datetime.now()
        cur = n.hour * 60 + n.minute; sv = sh * 60 + sm; ev = eh * 60 + em
        if sv == ev: return False
        if sv < ev: return sv <= cur < ev
        return cur >= sv or cur < ev
    except Exception:
        return False


def notify(title, body, sub=None):
    try:
        s = f'display notification "{body}" with title "{title}"'
        if sub: s += f' subtitle "{sub}"'
        subprocess.run(["osascript", "-e", s], capture_output=True, timeout=5)
    except Exception:
        pass


def discover(config):
    cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if not (cfg and ws): return []
    repos = []; seen = set()
    for p in cfg.get(config, "watched_repos.paths", []) or []:
        base = Path(p).expanduser()
        if not base.exists(): continue
        for cand in [base] + (list(base.iterdir()) if base.is_dir() else []):
            if not cand.is_dir(): continue
            r = ws.find_repo_root(cand)
            if r and r not in seen:
                seen.add(r); repos.append(r)
    return repos


def scan_all(config):
    ws = _imp("ws", ROOT / "scripts" / "worktree-state.py")
    if ws is None: return []
    return [ws.repo_summary(r) for r in discover(config)]


def classify_urgent(summaries, config):
    cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")
    if cfg is None: return []
    dt = cfg.get(config, "worktree.dirty_warn_count", 50)
    isec = cfg.get(config, "worktree.idle_warn_hours", 24) * 3600
    upt = cfg.get(config, "worktree.unpushed_warn_count", 5)
    urgent = []
    for s in summaries:
        for wt in s.get("worktrees", []):
            d = wt.get("dirty_count", 0) + wt.get("untracked_count", 0)
            up = wt.get("unpushed_count", 0)
            ats = wt.get("activity_ts") or 0
            age = time.time() - ats if ats else 0
            ip = wt.get("in_progress")
            r = []
            if ip: r.append(f"in-progress {ip}")
            if d >= dt: r.append(f"{d} dirty files")
            if up >= upt: r.append(f"{up} unpushed commits")
            if d > 0 and age > isec: r.append(f"dirty + idle {int(age/3600)}h")
            if r:
                wc = dict(wt); wc["_repo"] = s.get("repo"); wc["_reasons"] = r; urgent.append(wc)
    return urgent


def auto_wip_eligible(urgent, config):
    cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")
    led = _imp("ledger_v2", ROOT / "scripts" / "ledger-v2.py")
    if not (cfg and led): return []
    if not cfg.get(config, "auto_wip_save.enabled", True): return []
    cool = cfg.get(config, "auto_wip_save.cooldown_minutes", 15)
    elig = []
    for wt in urgent:
        if wt.get("in_progress"): continue
        if wt.get("dirty_count", 0) + wt.get("untracked_count", 0) == 0: continue
        try:
            recent = led.read_events(days=1, event_types=["wip_save"], worktree=wt.get("path"))
            if recent:
                last = max(e.get("ts", 0) for e in recent)
                if time.time() - last < cool * 60: continue
        except Exception:
            pass
        elig.append(wt)
    return elig


def run_auto_wip(elig):
    results = []
    script = ROOT / "scripts" / "wip-save.py"
    for wt in elig:
        try:
            r = subprocess.run([sys.executable, str(script), "--worktree", wt["path"], "--trigger", "monitor"],
                              capture_output=True, text=True, timeout=60)
            try: results.append(json.loads(r.stdout))
            except json.JSONDecodeError: results.append({"ok": False, "err": "non-JSON", "path": wt["path"]})
        except (subprocess.TimeoutExpired, OSError) as e:
            results.append({"ok": False, "err": str(e), "path": wt["path"]})
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", default="scan", choices=["scan", "digest", "auto-save"])
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    started = time.time()
    cfg = _imp("cfg", ROOT / "scripts" / "config-loader.py")
    led = _imp("ledger_v2", ROOT / "scripts" / "ledger-v2.py")
    if cfg is None: return 1
    config = cfg.load_config()
    summaries = scan_all(config)
    urgent = classify_urgent(summaries, config)
    saves = []
    if args.mode == "auto-save" or cfg.get(config, "auto_wip_save.enabled", True):
        elig = auto_wip_eligible(urgent, config)
        if elig: saves = run_auto_wip(elig)
    notifs = 0
    if args.mode == "digest":
        if cfg.get(config, "notification.enabled", True) and not in_quiet_hours(config):
            wts = sum(len(s.get("worktrees", [])) for s in summaries)
            sc = sum(1 for r in saves if r.get("ok") and r.get("branch_created"))
            body = [f"{wts} worktrees · {len(urgent)} need attention"]
            if sc: body.append(f"{sc} auto-saved overnight")
            notify("Ultraprompt — daily digest", " · ".join(body), "run /ultraprompt:status")
            notifs = 1
    elif args.mode == "scan":
        if urgent and cfg.get(config, "notification.enabled", True) and not in_quiet_hours(config):
            top = urgent[0].get("_reasons", ["urgent"])[0]
            notify("Ultraprompt — worktrees need attention",
                   f"{len(urgent)} worktree(s): {top}", "run /ultraprompt:status")
            notifs = 1
    dur_ms = int((time.time() - started) * 1000)
    if led and cfg.get(config, "ledger.enabled", True):
        led.write_event("monitor_run", mode=args.mode, repos_scanned=len(summaries),
                        worktrees_total=sum(len(s.get("worktrees", [])) for s in summaries),
                        urgent_count=len(urgent), notifications_sent=notifs,
                        auto_saves=len([r for r in saves if r.get("ok") and r.get("branch_created")]),
                        duration_ms=dur_ms)
    if not args.quiet:
        print(json.dumps({"mode": args.mode, "duration_ms": dur_ms,
                          "summaries_count": len(summaries), "urgent_count": len(urgent),
                          "auto_save_results": saves, "notifications_sent": notifs}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
