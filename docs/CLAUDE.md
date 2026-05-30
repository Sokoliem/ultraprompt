# Ultraprompt V9.3.0 Plugin Repo Notes

This file governs work on the Ultraprompt plugin itself, not work done by it.

## Current Shape

Ultraprompt is a Claude Code + Codex plugin with 56 skills, 35 agents, 33 commands, 42 MCP tools (all carrying full MCP-spec annotations: readOnlyHint/destructiveHint/idempotentHint/openWorldHint), 11 registered hooks (including the V9.0 PostToolUse evidence-ledger hook and the V9.1 vibe-detect UserPromptSubmit hook that auto-invokes the two-stage vibe picker), 12 panels, 18 artifact schemas, 2 output styles, live dashboard telemetry, local typed memory, safe dream jobs, governed learning, pathfinding, capability graph release gates, V8.6 picker prerequisites (route_suggest hook, YAML output schemas, auto-attached output styles, dispatching `build` skill backed by the `builder` agent with required claim-check gate, de-collided gap-analysis cluster, personal-lanes injection from `~/.claude/ultraprompt-user.md`), and (V8.7) an **interactive routing picker**: the route_suggest hook detects ambiguity (top-2 within 15% or top medium-confidence) and emits a directive instructing the model to invoke the new `ultraprompt:choose` skill; the new `route_picker` MCP tool returns ranked candidates with previews; the picker skill surfaces 3-4 options via AskUserQuestion (top + 2nd candidate + 2 LLM-rewritten prompt variants paired with their best-matching skills) and dispatches the chosen skill with the chosen phrasing.

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
- Build catalog metadata: `python3 scripts/build-catalog-metadata.py`
- Check catalog metadata: `python3 scripts/build-catalog-metadata.py --check`
- Build graph: `python3 scripts/build-capability-graph.py`
- Check graph: `python3 scripts/build-capability-graph.py --check`
- Router bench: `python3 scripts/run-router-bench.py`
- Pathfinder bench: `python3 scripts/run-pathfinder-tests.py`
- Cognitive integration: `python3 scripts/run-cognitive-tests.py`
- Hook fixtures: `python3 scripts/run-hook-tests.py`
- Hook coverage: `python3 scripts/audit-hook-coverage.py`
- Artifact tests: `python3 scripts/run-artifact-tests.py`
- Config tests: `python3 scripts/run-config-tests.py`
- MCP self-test: `python3 mcp/ultraprompt_meta.py --self-test`
- Full consistency: `python3 scripts/audit-catalog-consistency.py`
- Package validation: `python3 scripts/validate-plugin.py`
- Release scorecard: `python3 scripts/release-scorecard.py`
- Package zip: `python3 scripts/package-plugin.py`

## Invariants

- Runtime-neutral: no `model:`, `effort:`, or `context:` frontmatter pins.
- Local-first: V8 memory, events, dreams, and learning default to `~/.ultraprompt`.
- Evidence before memory: durable non-preference memory needs evidence.
- Proposal before mutation: dream and learning flows create candidates; they do not silently rewrite prompts, source specs, or user repos.
- Graph freshness is release-blocking.
- Every MCP mutation returns risk and confirmation metadata.
- Public docs must use `ultraprompt` and `/ultraprompt:*` command names.

## Release Flow

1. Make source or implementation changes.
2. Regenerate generated skills/agents as needed.
3. Rebuild skill index, catalog metadata, capability graph, catalog audit, and release scorecard.
4. Run `python3 scripts/audit-catalog-consistency.py`.
5. Run `python3 scripts/validate-plugin.py`.
6. Run `python3 scripts/package-plugin.py`.
7. Install to Claude Code and Codex with `scripts/install-windows.ps1 both` or `scripts/install.sh both`.
8. Run dashboard browser smoke against `/api/catalog`, `/api/cognitive/health`, `/api/pathfind`, and `/api/stream`.
