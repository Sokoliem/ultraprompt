# V8 Autonomy Layers

Ultraprompt V8 has six autonomy layers. Hooks are deterministic; runtime guidance files are heuristic. Anything safety-critical belongs in a hook, ledger, validator, or monitor rather than prose instructions.

## L1: In-Session Hooks

| Hook | When | Responsibility |
|---|---|---|
| `session-bootstrap.py` | SessionStart | Snapshot checkpoint and warn on dirty, unpushed, or concurrent work |
| `skill-agent-telemetry.py` | PreToolUse | Record skill and agent activation telemetry |
| `destructive-command-guard.py` | PreToolUse | Classify destructive command risk |
| `protected-file-guard.py` | PreToolUse | Guard protected paths |
| `auto-wip-save.py` | Stop | Save work when dirty growth crosses threshold |
| `stop-validation-check.py` | Stop | Catch unbacked validation claims |
| `session-finalize.py` | SessionEnd | Write session-end evidence |

All hooks fail open and respect `ULTRAPROMPT_DISABLE_HOOKS=1`.

## L2: Dual Runtime Parity

Claude Code and Codex share the same source plugin. Runtime-specific manifests and hook commands are selected during install. Ledger reads aggregate both `~/.claude/ultraprompt-data` and `~/.codex/ultraprompt-data`.

## L3: Cognitive Control Plane

V8 adds governed memory, dream reports, learning candidates, pathfinder routing, and the capability graph. Mutating cognitive actions are reviewable and reversible by design.

## L4: Dashboard

The dashboard shows catalog coverage, cognitive health, and live activity from runtime ledgers plus V8 cognitive JSONL streams.

## L5: Between-Session Monitor

The optional monitor scans watched repos, classifies urgency, and can surface daily digests or notifications.

## L6: Human Review Gates

Release scorecard, catalog audit, artifact schemas, pathfinder benches, hook fixtures, and docs drift checks provide the final governance layer before publishing.
