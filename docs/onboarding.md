# Ultraprompt Contributor Onboarding

This guide is for contributors working on the public `sokoliem/ultraprompt` repository.

## Prerequisites

- Python 3.11 or newer.
- PowerShell on Windows, or Bash on macOS/Linux.
- Claude Code and/or Codex if you want to install and exercise the plugin locally.

No package manager is required for the core plugin. The dashboard uses `aiohttp`; install it only if your Python environment does not already provide it.

## First Run

```bash
python3 scripts/build-skill-index.py
python3 scripts/build-catalog-metadata.py
python3 scripts/build-capability-graph.py
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
```

On Windows, use `python` or `py -3` if `python3` is not available.

## Architecture

- Skills, agents, and panels are catalog surfaces.
- MCP tools expose runtime actions to Claude Code and Codex.
- Hooks add safety checks, telemetry, WIP save, and session context.
- V8 cognitive state is local-first:
  - memory: typed facts, preferences, procedures, route outcomes, and hypotheses
  - events: append-only telemetry with trace and correlation IDs
  - dreams: scheduled reflection reports and proposals
  - learning: approval-gated, validated, reversible candidate queue
  - graph: generated capability map used by pathfinding and release gates

## Common Changes

To update a skill:

1. Edit `source/skill-specs.json`.
2. Run `python3 scripts/regenerate-skills.py`.
3. Run `python3 scripts/build-skill-index.py`.
4. Run `python3 scripts/audit-catalog-consistency.py`.

To update an agent:

1. Edit `source/agent-specs.json`.
2. Run `python3 scripts/regenerate-agents.py`.
3. Run `python3 scripts/build-skill-index.py`.
4. Run `python3 scripts/audit-catalog-consistency.py`.

To update a panel:

1. Edit `source/panel-specs.json`.
2. Keep the V8 contract fields complete: `mode`, `risk`, `confirmation`, `inputs`, `success_criteria`, `handoff_artifacts`, `phase_contracts`, `memory_policy`, `learning_policy`, `dream_policy`, `pathfinder_tags`, and `do_not_use_when`.
3. Run `python3 scripts/catalog-audit.py`.
4. Run `python3 scripts/build-capability-graph.py`.
5. Run `python3 scripts/build-catalog-metadata.py`.

To update V8 cognitive behavior:

1. Edit the relevant script in `scripts/`.
2. Update or add tests in `scripts/run-cognitive-tests.py` or `tests/pathfinder/`.
3. Rebuild `dist/capability-graph.json`.
4. Run `python3 scripts/run-cognitive-tests.py`.

## Release Checklist

```bash
python3 scripts/regenerate-skills.py --check
python3 scripts/regenerate-agents.py --check
python3 scripts/build-skill-index.py --check
python3 scripts/build-catalog-metadata.py --check
python3 scripts/build-capability-graph.py --check
python3 scripts/run-router-bench.py
python3 scripts/run-router-bench.py --adversarial
python3 scripts/run-router-bench.py --overlap-budget
python3 scripts/run-pathfinder-tests.py
python3 scripts/run-hook-tests.py
python3 scripts/run-config-tests.py
python3 scripts/run-artifact-tests.py
python3 scripts/run-cognitive-tests.py
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
python3 scripts/release-scorecard.py
```

## Local Install

Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 both
```

macOS/Linux:

```bash
bash scripts/install.sh both
```

Then restart Claude Code and Codex and run `/ultraprompt:doctor`.

## Dashboard Smoke

```bash
python3 scripts/dashboard.py --no-open
```

Open the reported localhost URL and verify:

- `/api/catalog` returns current counts.
- `/api/cognitive/health` is `ok: true`.
- `/api/pathfind?intent=review%20this%20plugin` returns a path.
- The live activity panel remains connected.

## Governance Rules

- Do not silently promote memory without evidence.
- Do not apply learning without validation.
- Do not let scheduled dream jobs mutate user repositories.
- Do not publish generated artifacts that fail their matching `--check` command.
