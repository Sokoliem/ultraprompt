# Ultraprompt

Ultraprompt is a local-first Claude Code and Codex plugin for senior engineering workflows. V8 adds a cognitive control plane on top of the proven catalog: typed memory, safe dream jobs, governed learning, workflow pathfinding, capability graph health, and a Mission Control dashboard.

**Version 8.0.0** | **48 skills** | **29 agents** | **42 MCP tools** | **30 commands** | **9 registered hooks** | **17 artifact schemas** | **12 panels** | **2 output styles**

## What It Does

- Routes messy engineering requests to focused skills, agents, panels, commands, and MCP tools.
- Runs V8 panels with explicit mode, risk, confirmation, input, success, handoff, phase-contract, and cognitive-policy metadata.
- Records evidence-led local telemetry for validation claims, routing outcomes, dashboard activity, and cognitive events.
- Stores typed long-term memory with scope, evidence, privacy class, lifecycle state, export, forget, and redaction controls.
- Runs safe dream jobs that summarize sessions, reflect on repos, learn from routing outcomes, inspect catalog health, and propose memory pruning.
- Queues learning candidates behind approval, validation, and reversible apply instead of silently mutating prompts or user repositories.
- Generates a capability graph over skills, agents, panels, commands, MCP tools, artifacts, validators, hooks, ledgers, and dream jobs.
- Ships a localhost dashboard for catalog health, live activity, cognitive health, memory, dreams, pathfinding, learning, and governance.

## Install

Windows PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 both
```

macOS/Linux:

```bash
bash scripts/install.sh both
```

After install, restart Claude Code and Codex, then run:

```text
/ultraprompt:doctor
/ultraprompt:dashboard
```

## V8 Commands

- `/ultraprompt:pathfind` explains the recommended skill, agent, command, panel, or staged workflow for an intent.
- `/ultraprompt:memory` queries and governs typed local memory.
- `/ultraprompt:dream` runs or inspects safe dream jobs.
- `/ultraprompt:dream-review` reviews dream reports and generated proposals.
- `/ultraprompt:learn-review` approves, applies, rejects, or reverts learning candidates.
- `/ultraprompt:graph` checks capability graph freshness and health.
- `/ultraprompt:mission-control` opens the cognitive dashboard.

## Validation

```bash
python3 scripts/build-skill-index.py --check
python3 scripts/build-catalog-metadata.py --check
python3 scripts/build-capability-graph.py --check
python3 scripts/regenerate-skills.py --check
python3 scripts/regenerate-agents.py --check
python3 scripts/run-pathfinder-tests.py
python3 scripts/run-cognitive-tests.py
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
python3 scripts/release-scorecard.py
```

## Local Data

Runtime state is local by default:

- `~/.ultraprompt/memory/memory.db`
- `~/.ultraprompt/memory/memory.jsonl`
- `~/.ultraprompt/events/events.jsonl`
- `~/.ultraprompt/dreams/reports/*.json`
- `~/.ultraprompt/learning/candidates.jsonl`
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
