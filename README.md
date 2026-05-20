# Ultraprompt

Ultraprompt is a local-first Claude Code and Codex plugin for senior engineering workflows. V8.6 hardens invocation reliability on top of V8.5 self-improvement: routing telemetry now steers cut-off handoff and auto-fire failures to the invocation review lane, strict release gates require live panel proof, route replay cannot pass on empty evidence, MCP scorecards report timeout state without stale fallbacks, and artifact-first agent handoff auditing checks persisted paths.

**Version 8.6.0** | **55 skills** | **31 agents** | **46 MCP tools** | **32 commands** | **9 registered hooks** | **31 artifact schemas** | **13 panels** | **2 output styles**

## What It Does

- Routes messy engineering requests to focused skills, agents, panels, commands, and MCP tools.
- Runs V8 panels with explicit mode, risk, confirmation, input, success, handoff, phase-contract, and cognitive-policy metadata.
- Records evidence-led local telemetry for validation claims, routing outcomes, dashboard activity, and cognitive events.
- Stores typed long-term memory with scope, evidence, privacy class, lifecycle state, export, forget, and redaction controls.
- Runs safe dream jobs that summarize sessions, reflect on repos, learn from routing outcomes, inspect catalog health, prune memory candidates, and invoke the gated self-improvement autopilot.
- Turns telemetry into auto-apply learning candidates and reversible local patches when evidence, eval, replay, and validation gates pass.
- Generates a capability graph over skills, agents, panels, commands, MCP tools, artifacts, validators, hooks, ledgers, and dream jobs.
- Ships a localhost dashboard for catalog health, live activity, cognitive health, memory, dreams, pathfinding, learning, gap lifecycle, panel runs, runtime readiness, and governance.

## Install

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 both
```

macOS/Linux:

```bash
bash scripts/install.sh both
```

After install, restart Claude Code and Codex. Claude Code exposes plugin slash commands:

```text
/ultraprompt:doctor
/ultraprompt:dashboard
/ultraprompt:self-improve run --mode dry-run --scope routing
```

Codex keeps `/` for native commands. Use `$ultraprompt:<skill>` for plugin skills and natural language or MCP tool names for command-backed operations. For example:

```text
$ultraprompt:dream run
$ultraprompt:dream status
$ultraprompt:self-improve run --mode dry-run --scope routing
```

## V8 Commands

- `/ultraprompt:pathfind` explains the recommended skill, agent, command, panel, or staged workflow for an intent.
- `/ultraprompt:memory` queries and governs typed local memory.
- `/ultraprompt:dream` runs or inspects safe dream jobs.
- `/ultraprompt:dream-review` reviews dream reports and generated proposals.
- `/ultraprompt:goal` applies a transcript-backed goal contract for Codex-compatible completion conditions; Codex gets bridge semantics, not a plugin-owned native evaluator loop.
- `/ultraprompt:learn-review` approves, applies, rejects, or reverts learning candidates.
- `/ultraprompt:self-improve` runs evidence-backed dry-run, canary, autopilot, and rollback.
- `/ultraprompt:graph` checks capability graph freshness and health.
- `/ultraprompt:mission-control` opens the cognitive dashboard.

## Validation

```bash
python3 scripts/build-skill-index.py --check
python3 scripts/generated-artifacts.py check
python3 scripts/build-routing-policy.py --check
python3 scripts/build-catalog-metadata.py --check
python3 scripts/build-capability-graph.py --check
python3 scripts/regenerate-skills.py --check
python3 scripts/regenerate-agents.py --check
python3 scripts/run-pathfinder-tests.py --no-telemetry
python3 scripts/run-cognitive-tests.py
python3 scripts/self-improve.py run --mode dry-run --scope routing
python3 scripts/replay-routing-events.py --json
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
python3 scripts/release-scorecard.py
python3 scripts/release-scorecard.py --check --target all --json
```

Use `--target all` for release decisions. It separates source, package, install simulation, active Codex cache, active Claude Code install, telemetry, artifact, and panel gates, and reports stale persisted scorecards without mutating active installs.

## Local Data

Runtime state is local by default:

- `~/.ultraprompt/memory/memory.db`
- `~/.ultraprompt/memory/memory.jsonl`
- `~/.ultraprompt/events/events.jsonl`
- `~/.ultraprompt/dreams/reports/*.json`
- `~/.ultraprompt/learning/candidates.jsonl`
- `~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl`
- `~/.ultraprompt/panels/<repo>/*-runs.jsonl`
- `~/.ultraprompt/learning/route-policy.json`

Environment overrides use the `ULTRAPROMPT__SECTION__KEY=value` form.

## Repository Map

- `source/skill-specs.json`: canonical skill specs.
- `source/agent-specs.json`: canonical agent specs.
- `source/panel-specs.json`: panel specs and graph metadata.
- `source/dream-jobs.json`: dream job catalog.
- `scripts/`: validators, installers, cognitive stores, pathfinder, release gates.
- `mcp/ultraprompt_meta.py`: MCP server and tool registry.
- `dashboard/`: browser UI served by `scripts/dashboard.py`.
- `dist/`: generated skill index, catalog metadata, capability graph, scorecards, and audit reports.

See [docs/onboarding.md](docs/onboarding.md) for the contributor path.
