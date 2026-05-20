# Ultraprompt V8.6.0 Plugin Repo Notes

This file governs work on the Ultraprompt plugin itself, not work done by it.

## Current Shape

Ultraprompt is a Claude Code + Codex plugin with 55 skills, 31 agents, 32 commands, 46 MCP tools, 9 registered hooks, 13 panels, 31 artifact schemas, 2 output styles, live dashboard telemetry, local typed memory, safe dream jobs, automated evidence-based self-improvement, source-derived routing policy, Invocation Director trigger plans, panel-aware pathfinding, route replay, experience-quality panels, goal contracts, invocation telemetry gates, reliability-classified release gates, artifact-first agent handoff auditing, fingerprinted gap ledger, panel run lifecycle, and capability graph release gates.

## Source Of Truth

- Skills: edit `source/skill-specs.json`, then run `python3 scripts/regenerate-skills.py`.
- Agents: edit `source/agent-specs.json`, then run `python3 scripts/regenerate-agents.py`.
- Panels: edit `source/panel-specs.json`.
- Dream jobs: edit `source/dream-jobs.json`.
- Catalog metadata: run `python3 scripts/build-catalog-metadata.py`.
- Capability graph: run `python3 scripts/build-capability-graph.py`.
- MCP tools: edit `mcp/ultraprompt_meta.py`.

Do not edit generated `skills/*/SKILL.md`, `agents/*.md`, `dist/skill-index.json`, `dist/catalog-metadata.json`, or `dist/capability-graph.json` without updating the source or generator.

## Validation Commands

- Regenerate skills: `python3 scripts/regenerate-skills.py`
- Check skills: `python3 scripts/regenerate-skills.py --check`
- Regenerate agents: `python3 scripts/regenerate-agents.py`
- Check agents: `python3 scripts/regenerate-agents.py --check`
- Build skill index: `python3 scripts/build-skill-index.py`
- Check skill index: `python3 scripts/build-skill-index.py --check`
- Build routing policy: `python3 scripts/build-routing-policy.py`
- Check routing policy: `python3 scripts/build-routing-policy.py --check`
- Build catalog metadata: `python3 scripts/build-catalog-metadata.py`
- Check catalog metadata: `python3 scripts/build-catalog-metadata.py --check`
- Build graph: `python3 scripts/build-capability-graph.py`
- Check graph: `python3 scripts/build-capability-graph.py --check`
- Generated artifact preflight: `python3 scripts/generated-artifacts.py check`
- Router bench: `python3 scripts/run-router-bench.py`
- Pathfinder bench: `python3 scripts/run-pathfinder-tests.py --no-telemetry`
- Invocation telemetry audit: `python3 scripts/audit-invocation-telemetry.py --json`
- Route replay: `python3 scripts/replay-routing-events.py --json`
- Self-improvement dry run: `python3 scripts/self-improve.py run --mode dry-run --scope routing`
- Cognitive integration: `python3 scripts/run-cognitive-tests.py`
- Hook fixtures: `python3 scripts/run-hook-tests.py`
- Hook coverage: `python3 scripts/audit-hook-coverage.py`
- Artifact tests: `python3 scripts/run-artifact-tests.py`
- Config tests: `python3 scripts/run-config-tests.py`
- MCP self-test: `python3 mcp/ultraprompt_meta.py --self-test`
- Full consistency: `python3 scripts/audit-catalog-consistency.py`
- Package validation: `python3 scripts/validate-plugin.py --target-runtime source --strict-runtime-files`
- Release scorecard: `python3 scripts/release-scorecard.py`
- Full runtime release scorecard: `python3 scripts/release-scorecard.py --check --target all --json`
- Package zip: `python3 scripts/package-plugin.py --verify-only`

## Invariants

- Runtime-neutral: no `model:`, `effort:`, or `context:` frontmatter pins.
- Local-first: V8 memory, events, dreams, and learning default to `~/.ultraprompt`.
- Evidence before memory: durable non-preference memory needs evidence.
- Evidence-gated mutation only: V8.5 self-improvement may mutate local repo files only through `scripts/self-improve.py` with run records, gate results, patch hashes, and rollback manifests. Ordinary dream and learning flows still create candidates unless the gated autopilot applies them.
- No automatic remote mutation: self-improvement never commits, pushes, installs, publishes, or mutates remotes.
- Graph freshness is release-blocking.
- Every MCP mutation returns risk and confirmation metadata.
- Public docs must distinguish runtime entrypoints: Claude Code uses `/ultraprompt:*` command names; Codex uses `$ultraprompt:<skill>`, natural language, or MCP tools because native `/` commands are not plugin-routed.
- Goal contracts must distinguish runtime semantics: Codex support is transcript-backed bridge discipline; Codex may also expose native built-in `/goal` evaluator behavior outside the plugin.

## Release Flow

1. Make source or implementation changes.
2. Regenerate generated skills/agents as needed.
3. Rebuild skill index, routing policy, catalog metadata, capability graph, catalog audit, and release scorecard. Use `--write-report` only when intentionally refreshing `dist/release-scorecard.json`; `--check` reports stale persisted evidence without mutating it.
4. Run `python3 scripts/audit-catalog-consistency.py`.
5. Run `python3 scripts/validate-plugin.py`.
6. Run `python3 scripts/package-plugin.py`.
7. Run `python3 scripts/release-scorecard.py --check --target all --json` to verify source, package, install simulation, active Codex cache, active Codex install, telemetry, artifact, and panel gates separately.
8. Install to Claude Code and Codex with `scripts/install-windows.ps1 both` or `scripts/install.sh both`.
9. Run dashboard browser smoke against `/api/catalog`, `/api/cognitive/health`, `/api/pathfind`, `/api/routing-effectiveness`, `/api/release-scorecard?target=all`, `/api/self-improvement/latest`, `/api/self-improvement/runs`, and `/api/stream`.
