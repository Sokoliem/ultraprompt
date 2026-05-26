# Changelog

## [9.1.0] - 2026-05-26

**V9.1.0 — vibe coding picker + SessionStart banner fix.** Turns open-ended
intents into a two-stage `AskUserQuestion` picker (lane → path) over a typed
`prompt_path_set.v1` artifact, then expands the chosen seed into a full
ready-to-run prompt. Ports the genesis vibe-coding pattern (`OptionTemplate`
schema, fingerprint dedup, char-limited fields) to the ultraprompt dispatch
architecture.

### Added

- **`skills/vibe/SKILL.md`** (tier=core, aliases: `vibe-coding`, `pick-direction`) — orchestrator. Dispatches `vibe-curator`, validates the artifact via `artifact_validate`, runs lane-then-path picker (collapses to one stage when only one lane has paths), expands the picked seed in evidence-led style. Never auto-executes.
- **`agents/vibe-curator.md`** (read-only, `maxTurns: 12`, tools: `Read, Grep, Glob`) — generates 4–8 paths across 2–4 lanes from the fixed taxonomy (`new-feature`, `refactor-or-cleanup`, `bug-fix-or-investigate`, `explore-or-prototype`). Each path carries lane, label, preview, seed, rationale, confidence, expected_files, expected_risk, and a deterministic 12-char fingerprint.
- **`hooks/recipes/vibe-detect.py`** (UserPromptSubmit) — phrase library + short-open-ended heuristic emits an `additionalContext` directive telling the model to invoke `/ultraprompt:vibe`. Honors `ULTRAPROMPT_DISABLE_HOOKS=1` and `hooks.vibe_detect_enabled`. Registered in both `hooks/hooks.json` and `hooks/hooks.windows.json`.
- **`artifact-schemas/prompt-path.schema.json`** — strict JSON Schema (draft 2020-12) with lane/confidence/risk enums and char caps matching genesis (`label≤80`, `preview≤120`, `seed≤200`, `rationale≤200`).
- **`scripts/artifact-validate.py`** — registered `prompt_path_set` schema; `scripts/run-artifact-tests.py` covers valid + invalid-missing-intent cases.
- **8 hook fixtures** under `tests/hooks/vibe-detect/` cover empty / trivial / already-routed / disabled / vibe-phrase / vibe-keyword / imperative-stays-silent / short-open-ended.
- **Config** in `source/config-defaults.toml`: `hooks.vibe_detect_enabled = true` and a new `[vibe]` section with `min_tokens`, `short_open_ended_max_tokens`, `min_paths`, `max_paths`, and the canonical `lanes` list.

### Fixed

- **SessionStart banner counts** in `hooks/recipes/session-bootstrap.py`: counts now correctly read from `dist/catalog-metadata.json["counts"]` instead of trying `data["skills"]` (a list of names) at the top level and silently falling back to hard-coded defaults. The banner had been stuck on `49 skills, 30 agents, 31 commands` regardless of catalog growth.

### Changed

- Counts: 55 → **56 skills** (new `vibe`), 34 → **35 agents** (new `vibe-curator`), 10 → **11 registered hooks** (new `vibe-detect.py`).
- Version bumped to `9.1.0` across `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `README.md`, `docs/CLAUDE.md`, and the session-start banner.

### Validation

- `scripts/run-hook-tests.py` → 57/57 fixtures pass (8 new).
- `scripts/run-artifact-tests.py` → all cases pass including the new prompt_path_set ones.
- `scripts/validate-plugin.py` → 0 errors.
- `scripts/audit-catalog-consistency.py` → 14/14 OK.

## [8.7.0] - 2026-05-23

**V8.7.0 — interactive routing picker.** Replaces the silent ambient nudge on
ambiguous prompts with a deliberate, visible selection moment: `AskUserQuestion`
with side-by-side previews of skill options and LLM-rewritten prompt variants,
followed by automatic dispatch of the chosen skill. Clear high-confidence
prompts keep the V8.6 silent nudge — no added friction.

### Added

- **Ambiguity branch** in `hooks/recipes/user-prompt-route-suggest.py` — calls `route_intent` with `limit=3`, computes top-1 vs top-2 score gap, and (a) when the gap is < `ambiguity_gap` (default `0.15`) or (b) when the top match is `medium` confidence, emits a directive instructing the model to invoke `ultraprompt:choose` before answering. Carries the top-3 candidate JSON inline so the picker skill doesn't have to re-score.
- **`route_picker` MCP tool** (`mcp/ultraprompt_meta.py`) — ranked candidates + previews extracted from each candidate's `## Distinctive judgment` + `## Output contract` sections, plus ambiguity metadata (`{gap, is_ambiguous}`).
- **`ultraprompt:choose` skill** (`skills/choose/SKILL.md`, tier=core, aliases: `pick`, `route-interactive`) — orchestrator skill. Calls `route_picker`, generates 2 LLM-rewritten prompt variants (re-routes each via `route_intent` to pair with their best-matching skill), builds an `AskUserQuestion` with up to 4 options (top + 2nd + 2 rewrites), and dispatches the chosen skill with the chosen phrasing. Handles `manual_only` skills by surfacing the slash command for the user to run.
- **`/ultraprompt:choose <intent>` slash command** (`commands/choose.md`) — manual invocation alongside the auto-trigger.
- **Telemetry**: `route_picker_triggered` (hook) and `route_picker_query` (MCP tool) and `route_picker_choice` (skill body) events flow through the existing `ledger-v2.py` to `/ultraprompt:dashboard` and `/ultraprompt:usage`. Feeds the learning queue with signal when users systematically prefer non-top routes.
- **Hook fixtures**: `06-ambiguous-prompt.json`, `07-picker-carries-inline-candidates.json`, `08-high-confidence-keeps-nudge.json` lock in both branches.

### Changed

- Version bumped to `8.7.0` across `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `marketplace.json`, `README.md`, `docs/CLAUDE.md`, MCP tool descriptions, agent header markers, and the session-start banner.
- `audit-doc-metadata.py` now finds `CLAUDE.md` at the plugin root OR under `docs/` (CLAUDE.md was relocated to `docs/` to satisfy the `claude plugin validate` advisory about root CLAUDE.md not being loaded as project context).
- Counts: 48 → **49 skills** (new `choose`), 42 → **43 MCP tools** (new `route_picker`), 29 → **30 commands** (new `/ultraprompt:choose`).

### Configuration

New `[route_suggest]` flags: `picker_enabled` (default `true`), `ambiguity_gap` (default `0.15`), `ambiguity_medium_confidence` (default `true`). All existing V8.6 flags still apply.

## [8.6.0] - 2026-05-23

**V8.6.0 — dispatch & quality discipline.** Closes the gap surfaced by the V8.0
adoption audit: dispatch policy and output discipline lived in docs the parent
session never loaded at decision time. V8.6 puts those decisions in front of
the model at arbitration time and makes every skill's output contract
machine-checkable.

### Added

- **UserPromptSubmit `route_suggest` hook** (`hooks/recipes/user-prompt-route-suggest.py`) — on each prompt, scores against the V8 skill index; when a specialist scores `high` and the prompt is not already routed, injects a single-line dispatch nudge into context. Fail-open, respects `ULTRAPROMPT_DISABLE_HOOKS=1`, configurable via `[route_suggest]` config block.
- **YAML output schemas** in every SKILL.md — `output_schema` field on each spec emits a structured `schema:` YAML block above the prose contract; each field declares `type`, `required`, and `evidence_rule`. Schema is authoritative for structure; output style is additive.
- **Output styles auto-attached** via skill frontmatter — every skill now declares `output_style: evidence-led` (default) or `output_style: concise-review` (review-shaped skills). Regenerator emits the binding in frontmatter and adds an "Output style" body section pointing to the matching `output-styles/<name>.md` file.
- **`ultraprompt:builder` agent** (`agents/builder.md`) — implements the build skill's discipline with a hard `claim_check` gate before declaring success. Returns files-changed, tests-added, validation-runs, claim-check-result, and remaining-assumptions.
- **Personal-lanes injection** — when `~/.claude/ultraprompt-user.md` exists, `session-bootstrap.py` injects its contents as the first arbitration signal. Template ships at `docs/personal-lanes-template.md`.
- **`migrate-skill-specs-v8-6.py`** — one-shot, idempotent migration that derives `output_schema` from existing pipe contracts, assigns `output_style`, and rewrites `description` to lead with the DEFAULT claim + name competing skills.

### Changed

- **Skill descriptions rewritten** — every skill's `description` now leads with `**DEFAULT for <X>: <verb-phrase>.**`, names competing slash commands explicitly (`/refactor`, `/migrate`, `/test-harden`, etc.), and pushes trigger phrases to the end. First seven words now carry the differentiator instead of `When user says 'X / Y / Z' —`.
- **Build skill rewritten** — dispatches to `ultraprompt:builder` for multi-file scope, stays inline for single-function tweaks, and gates success behind `claim_check` (no longer "may call" — required).
- **Gap-analysis cluster de-collided** — `gap-analysis` (ONE NAMED FEATURE end-to-end front door), `feature-completeness` (auditor only), `dead-code-drift` (drift only), `test-gap-analysis` (tests only), `repo-review` (whole repo) — each now leads with its disambiguator and an explicit "NOT THIS skill if …" pointer to its siblings.
- **`/route` and `/menu` auto-invokable** — removed `disable-model-invocation: true` so Claude can fall back to routing autonomously when the right specialist is ambiguous.
- **Session-start banner** rewritten to surface V8.6 dispatch defaults (including the new `build → builder` row) and the new inline-only list.
- Version bumped to `8.6.0` across `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `marketplace.json`, `README.md`, `CLAUDE.md`, MCP tool descriptions, and agent header markers.

### Configuration

New `[hooks]` flags: `route_suggest_enabled`, `output_style_inject_enabled`, `personal_lanes_enabled`. New `[route_suggest]` block (`min_tokens`, `min_score`, `accept_medium`, `only_unrouted`). New `[output_style].default = "evidence-led"`. New `[personal_lanes].file` and `max_chars`.

## [8.0.0] - 2026-05-11

**V8.0.0 - cognitive control plane.** Ships the full V8 local-first cognitive layer and renames the public project identity to `ultraprompt`.

### Added

- Typed local memory with SQLite storage, JSONL audit log, scope, evidence, privacy, lifecycle states, query, promotion, forget, export, import, and stats.
- Append-only cognitive event telemetry with trace IDs, correlation IDs, privacy controls, and secret blocking.
- Capability graph generation at `dist/capability-graph.json` covering skills, agents, panels, commands, MCP tools, artifacts, validators, hooks, ledgers, and dream jobs.
- Explainable pathfinding with memory influences, route-policy overlays, alternatives, risk/cost metadata, and deterministic golden tests.
- Safe dream engine with job catalog, session compaction, repo reflection, route learning, ecosystem reflection, memory prune, locks, reports, and no-repo-mutation tests.
- Governed learning queue with approval states, validation-before-apply, route policy overlays, reversible apply, and dashboard/CLI visibility.
- V8 MCP tools for memory, dreams, pathfinding, capability graph, learning candidates, learning apply, and route feedback.
- V8 commands: `/ultraprompt:memory`, `/ultraprompt:dream`, `/ultraprompt:dream-review`, `/ultraprompt:learn-review`, `/ultraprompt:pathfind`, `/ultraprompt:graph`, and `/ultraprompt:mission-control`.
- Five cognitive agents: `workflow-planner`, `memory-curator`, `dream-synthesizer`, `learning-auditor`, and `catalog-strategist`.
- Dashboard cognitive APIs and Mission Control home health for graph, memory, dreams, learning, events, and pathfinder.
- Public README and contributor onboarding documentation.

### Changed

- Version bumped to `8.0.0`.
- Public identity changed from `ultra-prompt` to `ultraprompt` across repo files, manifests, commands, installers, dashboard strings, and package output.
- Counts now report 48 skills, 29 agents, 42 MCP tools, 30 commands, 9 registered hooks, 17 artifact schemas, 8 panels, and 2 output styles.
- Release gates now block on capability graph freshness, pathfinder benchmarks, dream catalog validation, and cognitive integration tests.
- Windows install now rebuilds the capability graph before validating installed Claude Code and Codex copies.

## [7.2.0] - 2026-05-11

**V7.2.0 - trust consolidation.** Implements the next shippable milestone from the vNext cognitive PRD: release gates and source-of-truth hardening before cognitive automation is allowed to ship.

### Added

- Catalog metadata snapshot at `dist/catalog-metadata.json`, generated from `source/catalog/catalog.json` and the live plugin surfaces.
- Release-blocking `scripts/audit-catalog-consistency.py` covering skill index freshness, catalog metadata freshness, generated skills, generated agents, hook coverage, config env parsing, artifact enum validation, and current-state docs.
- `scripts/regenerate-agents.py --check`, with `source/agent-specs.json` populated for all 24 packaged agents.
- Hook coverage matrix in `tests/hooks/coverage.json`, audited by `scripts/audit-hook-coverage.py` and surfaced through dashboard health.
- Focused regression tests for V7 env overrides and artifact enum rejection.

### Fixed

- Config loading now applies `ULTRAPROMPT__SECTION__KEY=value` overrides and preserves underscores in keys such as `auto_wip_save.enabled`.
- Artifact validation now rejects invalid `severity`, `confidence`, `category`, `status`, and contract drift severity enum values.
- Gap ledger writes validate entries against the shared artifact contract before persisting.
- Codex install script now preserves `.codex-plugin/plugin.json` instead of copying the Claude manifest over it.
- Router boosts now distinguish release readiness from release notes, route test-gap and feature-gap prompts correctly, and handle migration wording such as Postgres version upgrades.

### Changed

- Current docs, manifests, marketplace metadata, dashboard command text, MCP dashboard description, release scorecard, and validation gates now report V7.2.0 with 48 skills, 24 agents, 29 MCP tools, 23 commands, 9 hooks, 8 panels, and 13 artifact schemas.

## [7.1.2] — 2026-05-11

**V7.1.2 — dashboard telemetry patch.** Fixes the live dashboard feed on Windows and across Claude Code/Codex installs by aligning the dashboard tailer with the ledgers the runtimes actually write.

### Fixed

- **Live Activity feed** now tails Claude ledger-v2 at `~/.claude/ultraprompt-data/events-YYYY-MM.jsonl`.
- **Codex activity support** now includes `~/.codex/ultraprompt-data/events-YYYY-MM.jsonl` and discovers new monthly/event files while the server is already running.
- **Legacy hook visibility** now includes the V5 evidence ledger at `~/.claude/plugins/data/ultraprompt/evidence-ledger.jsonl`.
- **Dashboard startup history** now replays recent existing telemetry instead of showing an empty feed until the next event.
- **Edge-case handling** now ignores malformed JSONL, normalizes ISO timestamps, handles truncation/rotation, and keeps `/api/health` available for diagnostics.
- **Windows logging** now falls back to stdout if `~/.ultraprompt/logs/dashboard.log` is locked or permission-blocked.
- **Version surfaces** bumped to `7.1.2` across Claude/Codex manifests, MCP server info, release scorecard, generated skill index, and install manifests.

## [7.1.1] — 2026-05-10

**V7.1.1 — live dashboard.** Adds a localhost browser dashboard that surfaces the full plugin ecosystem (24 agents, 48 skills, 8 panels, 29 MCP tools, 23 commands, 13 artifact schemas) with streaming invocation telemetry from the evidence ledger. Auto-launches via `/ultraprompt:dashboard`.

### What's new

- **`/ultraprompt:dashboard` command** — launches a 3-pane localhost UI at `http://localhost:5174/` (auto-scans 5174-5199 for free port). Idempotent; re-running opens existing instance.
- **`scripts/dashboard.py`** — single-file aiohttp server. Endpoints: `/api/catalog`, `/api/catalog/<kind>/<name>`, `/api/audit`, `/api/router-bench`, `/api/invocations`, `/api/mission-state`, `/api/stream` (Server-Sent Events), `POST /api/validate`.
- **`dashboard/` static assets** — vanilla JS Web Components (`<up-stats-card>`, `<up-catalog-tree>`, `<up-detail-pane>`, `<up-activity-feed>`), single-file `app.js` + `styles.css` + `index.html`. No build step.
- **3 new MCP tools** (29 total, +3):
  - `dashboard_launch` — spawn the server, wait for health, auto-open browser
  - `dashboard_status` — pid/port/url query
  - `dashboard_stop` — clean shutdown

### Dashboard UX

- **Left pane**: catalog tree grouped by kind (skills/agents/panels/MCP tools/commands/artifact schemas), each item color-coded by kind, with tier badges (core/specialist/ecosystem). Search box at top with `⌘K` shortcut. Ecosystem stats card above tree (clickable to scroll to that kind).
- **Center pane**: entity detail — description, extracted trigger phrases, distinctive judgment (skills), first signals, failure modes, workflow steps, output contract, lane boundaries (agents), anti-patterns, phased dispatch visualization (panels), input schema (MCP tools), schema (artifact schemas), recent invocations from ledger.
- **Right pane**: live activity feed via SSE. Replay of last 50 events on connect, then real-time stream. Event kinds: `evidence_graph_node`, `evidence_graph_edge`, `mission_state`, `evidence`. Slide-in animation, max 100 events, click to log full payload to console.
- **Top bar**: brand, plugin version, search, live stream indicator (connecting/live/error dot), refresh button.
- **Footer**: total catalog items, current audit finding count.

### Technical

- **Stack**: Python 3.11+ / aiohttp / vanilla JS Web Components. No frontend framework, no build pipeline.
- **State files**: `~/.ultraprompt/state/dashboard.pid`, `~/.ultraprompt/state/dashboard.port`.
- **Logs**: `~/.ultraprompt/logs/dashboard.log`.
- **Telemetry sources**: tails `~/.ultraprompt/evidence-graph/{nodes,edges}.jsonl`, `~/.ultraprompt/state/mission-state-history.jsonl`, `~/.ultraprompt/evidence/*.jsonl` every 500ms.
- **Catalog caching**: in-memory with mtime invalidation on `source/skill-specs.json`, `source/panel-specs.json`, `agents/`, `commands/`, `mcp/ultraprompt_meta.py`. Stat check every 5s.
- **Audit caching**: 30s TTL. Router bench caching: 5min TTL.
- **Port strategy**: default 5174; fallback scans 5174-5199. Port persisted in `dashboard.port` for stable URLs across restarts.
- **Process model**: `subprocess.Popen` with `start_new_session=True`. PID file for liveness check. SIGTERM on stop.
- **Security**: 127.0.0.1 bind only. No auth (single-user). No write endpoints to filesystem state. No outbound network calls.
- **Performance**: catalog endpoints <50ms after warm-up; SSE event delivery <1s from ledger write; <50MB Python process memory; <2% idle CPU.

### Prerequisites

`aiohttp` Python package. Lazy-installed on first launch with explicit prompt. Once installed, no per-launch dependency check.

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing state files (mission-state, gap ledger, evidence graph) consumed read-only.

### Validators

| Check | Result |
|---|---|
| Schema audit | ✓ 0 errors |
| Duplication audit | ✓ 0 errors |
| Skill tier audit | ✓ core 28 / specialist 15 / ecosystem 5 |
| Drift audit | ✓ 0 stale refs |
| Catalog audit | ✓ 0 findings |
| Router bench | ✓ 98.0% top-1, 100% top-3, 100% adversarial rejection |
| Dashboard endpoints | ✓ all 9 endpoints respond correctly |
| Dashboard launch/stop | ✓ idempotent, clean SIGTERM |
| MCP self-test | ✓ 29 tools |
| Release scorecard | ✓ READY |

### Deferred to V2 (PRD non-goals locked)

- Interactive dispatch from UI (clicking a skill to run it) — requires Claude Code / Codex IPC bridge
- Authentication, multi-user, remote access
- Edit catalog from UI
- Persistent analytics beyond ledger lifetime

---

## [7.1.0] — 2026-05-10

**V7.1 — robustness + product/innovation expansion.** Lands the V7.1 quality pack (catalog audit, artifact validator, evidence graph foundation, 2 new MCP tools, doctor updates) and the product/innovation lane (3 agents, 5 skills, 2 panels). Audits the entire V7.0 catalog and lifts every agent and skill to the V7.1 robustness bar: **124 → 0 findings**, zero critical, zero high.

### V7.0 → V7.1 cumulative changes

| | V7.0 | **V7.1** | Δ |
|---|---|---|---|
| Agents | 21 | **24** | +3 |
| Skills | 43 | **48** | +5 |
| Commands | 22 | 22 | 0 |
| MCP tools | 24 | **26** | +2 |
| Hooks | 9 | 9 | 0 |
| Panels | 6 | **8** | +2 |
| Artifact schemas | 0 | **13** | new |
| Catalog audit findings | (not run) | **0** | new |

### Audit pass: 124 → 0 findings

Built `catalog-audit.py` as part of V7.1's quality pack and ran it against the V7.0 catalog. Initial: 124 findings (0 critical, 37 high, 65 medium, 22 low). Top issue types: 31× no_trigger_phrasing, 22× no_default_claim, 19× description_short, 16× no_lane_boundaries, 9× no_output_contract_section.

Closed all findings in this release:

- **9 V5/V6 agents rewritten to V7 quality bar**: `debugger`, `reviewer`, `scout`, `adversarial`, `auditor`, `router`, `security-auditor`, `test-strategist`, `writer`. Each now has: USE WHEN/DO NOT/DEFAULT description framing, required output contract YAML, discipline section, lane boundaries table, anti-patterns, output format. Bodies now ~4-5KB each (was ~1KB).
- **34 V5/V6 skill descriptions upgraded** to V7 framing: `review`, `debug`, `ci-repair`, `build`, `refactor`, `migrate`, `release`, `security-audit`, `database-review`, `llm-eval-design`, `mcp-design`, `hooks-design`, `agent-author`, `skill-author`, `plugin-review`, `docs-sync`, `contract-test-generate`, `technical-debt-triage`, `tui-design-innovate`, `accessibility-review`, `ai-agent-safety-review`, `api-contract`, `architect`, `data-flow-privacy-map`, `dependency-audit`, `infra-iac-review`, `observability-pass`, `performance-pass`, `state-machine-review`, `supply-chain-hardening`, `test-harden`, plus `test-gap-analysis` when-to-use expansion.
- **7 V7-alpha agents got explicit Lane boundaries tables**: `repo-cartographer`, `feature-completeness-auditor`, `wiring-gap-inspector`, `gap-analysis-lead`, `integration-contract-reviewer`, `test-gap-analyst`, `release-readiness-auditor`.
- **PRD output contracts expanded**: `prd-technical` and `prd-ai-feature` output_contract strings now itemize technical_design and AI-specific subsections explicitly.

Final audit pass: **0 findings across all severities.**

### V7.1 quality pack

**`scripts/catalog-audit.py`** (governance) — robustness check for every agent and skill. Audits: description length and specificity, USE WHEN/DO NOT/DEFAULT clauses, output contract sections, anti-patterns, lane boundaries, discipline sections, body length, spec required fields, when_to_use / distinctive_judgment / failure_modes / workflow_steps lengths, output_contract structure, dispatch_to references resolving to existing agents, panel references resolving, duplicate descriptions. Severity ladder: critical / high / medium / low. Exit code reflects severity.

**`scripts/artifact-validate.py`** (PRD §28) — validates structured artifacts against schemas. Catches the "fluffy artifact" failure mode (PRD §35 HIGH risk). 13 schemas shipped: `prd_lite`, `prd_standard`, `prd_technical`, `prd_ai_feature`, `gap_ledger_entry`, `repo_review_report`, `release_readiness_report`, `contract_drift_report`, `opportunity_map`, `idea_triage`, `concept_brief`, `mvp_scope`, `problem_framing`. Validates required sections, enum values, min counts, nested required fields.

**`scripts/evidence-graph.py`** (PRD §10.2) — evidence graph v3 foundation. Lightweight provenance layered on top of ledger v2 (which stays canonical). Nodes: claim / validation / artifact with auto-generated kind:hash IDs. Edges: derived-from / validates / refutes / supports / contradicts. Storage: `~/.ultraprompt/evidence-graph/{nodes,edges}.jsonl`. Subcommands: write-claim, write-validation, write-artifact, link, query, path, stats. Reversible migration; ledger v2 remains canonical for V7.1.

**2 new MCP tools** (24 → 26):
- `artifact_validate` — without args: returns schema list; with `artifact_type` alone: returns that schema; with both: validates.
- `catalog_audit` — runs catalog-audit.py and returns structured findings JSON. Designed for CI and pre-release governance.

**`commands/doctor.md` updated** with 6 V7.1 sections: catalog robustness audit, artifact contracts, evidence graph foundation, mission control state freshness, install manifest verify, panel catalog audit.

### V7.1 product/innovation lane

**3 new agents** (PRD §13):
- `market-analyst` (4731B) — competitive analysis, white-space mapping, TAM/SAM/SOM with sensitivity analysis. Three output schemas (competitive_analysis, white_space_map, market_sizing).
- `innovation-lead` (5649B) — idea generation (SCAMPER, JTBD, constraint-removal, analogy, first-principles, inversion), idea triage with weighted criteria, problem framing reframings. Three output schemas (idea_generation, idea_triage, problem_framing).
- `customer-advocate` (5022B) — customer signal interpretation, fit assessment, disconnect identification between team and customer. Two output schemas (customer_perspective, customer_signal_analysis).

**5 new product/innovation skills** (PRD §17), all tier=core, family=product-innovation:
- `/ultraprompt:opportunity-map` → market-analyst — opportunity space exploration with market/competitive/customer axes
- `/ultraprompt:idea-triage` → innovation-lead — rank existing ideas with weighted criteria (impact, fit, effort, evidence, risk)
- `/ultraprompt:concept-brief` → principal-pm — concept-stage one-pager with differentiator + decision required
- `/ultraprompt:mvp-scope` → principal-pm — hypothesis-driven MVP scope with must/should/won't + post-MVP roadmap
- `/ultraprompt:problem-framing` → innovation-lead — reframe problem with multiple lenses (JTBD, constraints, segment, substitutes, time horizon)

**2 new panels** (PRD §21):
- `idea-panel` — frame → ground (customer-advocate + market-analyst, parallel) → generate_and_triage → validate_recommendation; 5 dispatches across 4 phases, high cost, ~20 min
- `mvp-panel` — scope → feasibility_and_evaluation (technical-product-architect + evaluator, parallel) → synthesize; 4 dispatches across 3 phases, medium cost, ~15 min

### Migration

Drop-in via `scripts/install.sh both`. No config changes. V7.0 evidence ledger continues; new evidence graph foundation is additive. Existing backups created automatically; install manifest written for future rollback. Catalog audit findings start at 0 — any regression in future releases will be visible immediately.

### Validators (V7.1)

| Check | Result |
|---|---|
| Schema audit (auto-detect Claude/Codex) | ✓ 0 errors |
| Plugin validator | ✓ 0 errors |
| Duplication audit | ✓ 0 errors |
| Skill tier audit | ✓ core 28, specialist 15, ecosystem 5 |
| Drift audit | ✓ 0 stale refs |
| **Catalog audit** | ✓ **0 findings (down from 124)** |
| Router bench (49 cases) | ✓ 100% top-3 |
| Router bench adversarial | ✓ 12/12 rejected |
| Hook fixtures | ✓ 26/26 |
| Destructive guard fixtures | ✓ 16/16 |
| WIP snapshot fixtures | ✓ 10/10 |
| Install manifest write/verify/rollback | ✓ |
| Mission Control snapshot | ✓ 8 panels surfaced |
| Panel plan dispatch | ✓ all panels resolvable |
| Artifact validator | ✓ 13 schemas, smoke-tested |
| Evidence graph foundation | ✓ smoke-tested |
| MCP self-test | ✓ 26 tools |
| Release scorecard | ✓ READY |

### V7.1 north star alignment

PRD §48 says Ultraprompt should help the user discover what to build, specify it clearly, test the idea, implement safely, audit for gaps, and prove what was validated. V7.1 lifts the **discover-what-to-build** lane (5 product-innovation skills + 3 agents + 2 panels) and the **prove-what-was-validated** lane (artifact validator + evidence graph foundation + catalog audit). The remaining experiment / strategy / roadmap families land in V7.2+.

---

## [7.0.0] — 2026-05-10

**V7.0 — final release.** Lands the PRD's minimum viable V7 (§36) plus everything from alpha.1-4. Closes Phase 0 trust pack, ships the repo-completeness pack (8 agents, 8 skills coverage), Mission Control + panels + gap-ledger, and adds the PRD/product family minimum (4 agents, 5 skills, 2 panels).

### V7.0 vs V6.6 — cumulative changes

| | V6.6 | **V7.0** | Δ |
|---|---|---|---|
| Agents | 9 | **21** | +12 |
| Skills | 32 | **43** | +11 |
| Commands | 20 | **22** | +2 |
| MCP tools | 18 | **24** | +6 |
| Hooks | 9 | 9 | 0 |
| Test fixtures | 26 | 52 | +26 |
| Panels | 0 | **6** | +6 |
| Phase 0 trust items | 0/7 | **7/7** ✓ | complete |
| Repo-completeness pack | 0/8 | **8/8** ✓ | complete |

### What's new in V7.0 (this release, vs alpha.4)

**4 new product agents** (PRD §13):
- `principal-pm` — lead product strategy, PRD drafting, requirements clarification
- `technical-product-architect` — product-to-technical translation with traceability
- `evaluator` — eval plans, success criteria, experiment design, hypothesis-testing methodology
- `risk-and-controls-reviewer` — compliance, regulatory, privacy, operational risk; financial-services-aware

**5 new PRD skills** (PRD §18):
- `/ultraprompt:prd-lite` — 1-2 page structured product brief for early thinking
- `/ultraprompt:prd-standard` — full PRD with problem/users/goals/scope/risks/metrics/acceptance/rollout/validation/open-questions
- `/ultraprompt:prd-technical` — PRD oriented around technical design (chains principal-pm + technical-product-architect)
- `/ultraprompt:prd-ai-feature` — AI/LLM/agent feature spec (chains 4 agents: principal-pm + technical-product-architect + evaluator + risk-and-controls-reviewer)
- `/ultraprompt:prd-to-plan` — convert approved PRD to phased implementation plan

**2 new panels** (PRD §21):
- `prd-panel` — product → technical+measurement (parallel) → risk → synthesize; 5 dispatches, ~22 min, high cost
- `ai-feature-panel` — product → technical+evaluator (parallel) → security+risk (parallel) → synthesize; 6 dispatches, ~28 min, high cost. The full chain for any LLM/agent/ML feature.

### Cumulative V7.0 features (alpha.1 → V7.0)

**Trust pack (PRD Phase 0)** — all 7 items shipped:

| § | Item | Landed |
|---|---|---|
| §8.1 | Verified WIP snapshot + 10/10 fixtures | alpha.2 + alpha.3 |
| §8.2 | `ULTRAPROMPT__SECTION__KEY` env override | alpha.1 |
| §8.3 | Native `.codex-plugin/plugin.json` | alpha.1 |
| §8.4 | Drift audit | alpha.1 |
| §8.5 | Duplication budget via `_shared/DISPATCH-POLICY.md` | alpha.2 |
| §8.6 | Installer rollback hardening with sha256 manifest | alpha.4 |
| §8.7 | Destructive guard 4-class risk classifier | alpha.2 |

**Repo-completeness pack (PRD §14)** — all 8 specialists shipped:

| Agent | Lane |
|---|---|
| repo-cartographer | Structured repo map for downstream consumers |
| feature-completeness-auditor | Single-feature E2E completeness |
| wiring-gap-inspector | Orphan-producer scan across all layers |
| integration-contract-reviewer | Producer-consumer mismatch (API, schema, event, webhook) |
| test-gap-analyst | Risk-weighted missing coverage |
| dead-code-and-drift-hunter | Stale/dead/duplicate with safe-to-remove labels |
| release-readiness-auditor | Ship/risky/blocked verdict with phased remediation |
| gap-analysis-lead | Multi-source synthesis with dedupe and sequencing |

Plus 5 audit skills wired to persist findings via `gap_ledger_write`: `gap-analysis`, `feature-completeness`, `test-gap-analysis`, `dead-code-drift`, `release-readiness`.

**Orchestration layer:**

- **6 first-class panels** with phased dispatch (sequential and parallel) — see panel list above
- **Mission Control** unified state across 7 stores (repo capsule, worktree, sessions, evidence ledger, validation, WIP snapshots, gap ledger)
- **Gap ledger persistence** at `~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl` with query/write/stats MCP tools
- **Release scorecard** for plugin shipability (manifests, discovery, routing, safety, drift)

**New MCP tools** (alpha.1-4 added 6 tools, total now 24):

- `release_scorecard` — plugin release-readiness check
- `panel_plan` — get phased dispatch plan for any panel
- `mission_state` — unified state snapshot
- `gap_ledger_query` — filter persistent gaps
- `gap_ledger_write` — persist findings to gap ledger
- `gap_ledger_stats` — totals by status/severity/category/repo

### Validators (V7.0)

| Check | Result |
|---|---|
| Schema audit (auto-detect Claude/Codex) | ✓ 0 errors |
| Plugin validator | ✓ 0 errors |
| Duplication audit | ✓ 0 errors |
| Skill tier audit | ✓ core 23, specialist 15, ecosystem 5 |
| Drift audit | ✓ 0 stale refs |
| Router bench (49 cases) | ✓ 100% top-3 |
| Router bench (adversarial) | ✓ 12/12 rejected |
| Hook fixtures | ✓ 26/26 |
| Destructive guard fixtures | ✓ 16/16 |
| WIP snapshot fixtures | ✓ 10/10 |
| Install manifest write/verify/rollback | ✓ smoke-tested |
| Mission Control snapshot | ✓ reads 7 stores |
| Panel plan dispatch | ✓ 6 panels resolvable |
| MCP self-test | ✓ 24 tools |
| Release scorecard | ✓ READY |

### Honest scope assessment

This V7.0 ships the PRD §36 "minimum viable V7.0" definition:

| §36 item | Status |
|---|---|
| Trust fixes | ✓ all 7 |
| Native Claude/Codex manifests | ✓ |
| Mission Control status | ✓ |
| Evidence graph/proof-card foundation | **deferred** to V7.1 |
| Existing skill/agent revision contracts | ✓ |
| Repo completeness agent pack | ✓ 8/8 |
| Repo completeness skills and commands | ✓ |
| PRD family minimum (5 skills) | ✓ |
| Product minimum (5 skills) | ✓ (PRD family counts) |
| Panels minimum (5 panels) | ✓ (6 shipped) |
| Release scorecard | ✓ |

**Deferred to V7.1+:**
- Evidence graph v3 migration (PRD §10.2) — ledger v2 stays canonical for V7.0
- Remaining product/innovation skills beyond PRD family (PRD §17) — opportunity-map, idea-triage, concept-brief, mvp-scope, white-space-analysis, strategy-brief, competitive-teardown, roadmap-options, innovation-sprint, problem-framing
- Experiment skill family (PRD §17.3) — experiment-design, ab-test-plan, prototype-test-plan, metric-tree, assumption-test, experiment-readout, causal-risk-review, llm-product-eval-plan
- Remaining product agents (PRD §13.1-13.4) — 17 more
- 5 more product panels (PRD §21.1) — idea-panel, experiment-panel, mvp-panel, enterprise-feature-panel, iteration-panel
- Artifact contracts validator (PRD §28)
- Catalog audit MCP tool (PRD §27.4)
- Repo-completeness fixture repos (PRD §32.2)
- Router golden tests for all alpha.2-4 skills (PRD §27.3)

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically; install manifest written for future rollback. Schema and skill-tier expectations updated automatically.

After install: start a NEW session for V7.0 directive + all new agents/skills/panels/MCP tools to take effect together.

### V7.0 north star (PRD §48)

> Ultraprompt should not only help the user code. It should help the user discover what to build, specify it clearly, test the idea, implement it safely, audit the repo for gaps, and prove what was validated.

V7.0 covers: specify clearly (PRD family), audit for gaps (repo-completeness pack), prove what's validated (gap-ledger persistence + Mission Control). The "discover what to build" and "test the idea" lanes land in V7.1+ via the product/innovation/experiment families.

---

## [7.0.0-alpha.4] — 2026-05-10

V7 orchestration layer: panels become first-class, Mission Control unifies state, auditors persist findings, installer rollback closes Phase 0. Transforms 17 disconnected agents into a coordinated bench.

### New: Panel system as first-class (PRD §21)

- **`source/panel-specs.json`** — 4 panels with phased dispatch strategy:
  - `repo-completeness-panel` — 8 agents (cartographer + 6 specialists + lead), ~25 min, high cost; full whole-repo audit
  - `feature-gap-panel` — 5 agents (cartographer + 3 specialists + lead), ~12 min, medium cost; single-feature E2E
  - `contract-drift-panel` — 4 agents (cartographer + 2 specialists + lead), ~10 min, medium cost; API/schema/event drift
  - `release-gate-panel` — 6 agents (cartographer + 4 specialists + lead), ~18 min, high cost; ship/no-ship verdict
- Each panel declares phases (sequential vs parallel), purpose per phase, output artifact, gap-ledger writeback, cost+time estimates.
- **`panel_plan` MCP tool (NEW)** — returns dispatch plan with task briefs and synthesis strategy. Without args: catalog list. With `panel_name` + optional `scope`: phased plan.
- **`/ultraprompt:panel-run` command upgraded** — V7 panel orchestration: parallel phases dispatch all agents in single message; sequential phases wait between dispatches; synthesis-phase agent receives all upstream output. Cost gating for high-cost panels.
- **`team_plan` MCP tool aliased** — backwards compatibility for V6 callers; description marks alias.

### New: Mission Control state model (PRD §9.2)

- **`scripts/mission-state.py`** — unified state aggregator. Reads from:
  - Plugin manifest + runtime detection (Claude/Codex)
  - Repo + worktree state via existing `worktree-state.py`
  - Active sessions via `worktree-state.find_active_sessions`
  - Evidence ledger v2 (24h event types + counts)
  - WIP snapshots (git branches under `wip/<repo>/*`)
  - Gap ledger summary (totals by status/severity/repo)
  - Available panels from panel-specs.json
- Persists to `~/.ultraprompt/state/mission-state.json` + appends to `mission-state-history.jsonl` for trend analysis.
- **`mission_state` MCP tool (NEW)** — returns the unified snapshot. Optional `write` param to persist.
- **`/ultraprompt:mission` slash command (NEW)** — formats Mission Control snapshot as readable summary. Use at session start, after long breaks, or before deciding panel runs.

### New: Auditor → gap-ledger persistent integration

- **3 new MCP tools** wire the alpha.3 storage into agent workflows:
  - `gap_ledger_query` — filter by repo/status/severity/limit; agents check existing gaps before adding duplicates
  - `gap_ledger_write` — persist a finding to `~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl`; required: repo, title; optional: full schema
  - `gap_ledger_stats` — totals by status/severity/category/repo/auditor
- **5 audit skills updated with workflow_steps** that explicitly call `gap_ledger_write` after synthesis: `gap-analysis`, `feature-completeness`, `test-gap-analysis`, `dead-code-drift`, `release-readiness`. Each skill now produces persistent state across sessions, queryable via `gap_ledger_query` and surfaced in Mission Control.

### New: Installer rollback hardening (PRD §8.6 — closes Phase 0)

- **`scripts/install-manifest.py`** — install/verify/rollback module:
  - `write` records sha256 + size for every installed file at `<install-root>/.ultraprompt-install-manifest.json`
  - `verify` walks install tree, compares sha256 to manifest; reports drift + missing files
  - `rollback --confirm` stashes current install, restores from declared backup_root, verifies restoration
- **`install-claude-code.sh` and `install-codex.sh` patched** — manifest writer runs after successful install, declares backup_root for future rollback.
- Smoke-tested at install time: write → modify → verify catches drift → rollback restores.

### Final V7 trust pack status (PRD Phase 0)

| § | Item | Status |
|---|---|---|
| §8.1 | Verified WIP snapshot + 10/10 fixtures | ✓ alpha.2 + alpha.3 |
| §8.2 | Env override `__` parser | ✓ alpha.1 |
| §8.3 | Native Codex manifest | ✓ alpha.1 |
| §8.4 | Drift audit | ✓ alpha.1 |
| §8.5 | Duplication budget | ✓ alpha.2 |
| §8.6 | **Installer rollback hardening** | ✓ **alpha.4** (this release) |
| §8.7 | Destructive command guard risk classifier | ✓ alpha.2 |

**Phase 0 complete: 7/7 items shipped.**

### Counts (cumulative)

| | V6.6 | alpha.1 | alpha.2 | alpha.3 | alpha.4 |
|---|---|---|---|---|---|
| Agents | 9 | 10 | 13 | 17 | **17** |
| Skills | 32 | 33 | 35 | 38 | **38** |
| Commands | 20 | 21 | 21 | 21 | **22** (+/ultraprompt:mission) |
| MCP tools | 18 | 19 | 19 | 19 | **24** (+5: panel_plan, mission_state, gap_ledger_query/write/stats) |
| Hooks | 9 | 9 | 9 | 9 | 9 |
| Test fixtures | 26 | 26 | 42 | 52 | 52 |
| Panels | 0 | 0 | 0 | 0 | **4** |
| Repo-completeness pack | 0/8 | 1/8 | 4/8 | 8/8 | 8/8 |
| Phase 0 trust items | 0/7 | 4/7 | 6/7 | 6/7 | **7/7** |

### Validators

- Schema audit (auto-detect): ✓
- Plugin validator: ✓ 0 errors
- Duplication audit: ✓ 0 errors
- Skill tier audit: ✓
- Drift audit: ✓ 0 stale refs
- Router bench: ✓ 100% top-3
- Hook fixtures: ✓ 26/26
- Destructive guard fixtures: ✓ 16/16
- WIP snapshot fixtures: ✓ 10/10
- Install manifest smoke test: ✓ write/verify/drift-detection/rollback
- Mission Control snapshot: ✓ reads 7 state stores

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically; install manifest written for future rollback.

After install: start a NEW session for V7.0.0-alpha.4 directive + new panel/mission commands + updated audit skill workflows + new MCP tools to take effect together.

---

## [7.0.0-alpha.3] — 2026-05-10

V7 repo-completeness pack complete (8/8 specialist agents). Plus persistent gap-ledger storage and the full WIP snapshot fixture suite from PRD §8.1.

### New (V7 repo-completeness pack now 8/8)

| Agent | Status | Lane |
|---|---|---|
| repo-cartographer | alpha.1 | Structured repo map for downstream consumers |
| feature-completeness-auditor | alpha.2 | Single-feature end-to-end audit |
| wiring-gap-inspector | alpha.2 | Orphan-producer scan |
| gap-analysis-lead | alpha.2 | Multi-source synthesis |
| **integration-contract-reviewer** | **alpha.3** | Producer-consumer mismatch detection |
| **test-gap-analyst** | **alpha.3** | Risk-weighted missing coverage |
| **dead-code-and-drift-hunter** | **alpha.3** | Stale/dead/duplicate code with safe-to-remove labels |
| **release-readiness-auditor** | **alpha.3** | Ship/risky/blocked verdict with phased remediation |

The 4 alpha.3 agents each ship with: distinct trigger phrasing, structured YAML output contract, severity rules, evidence requirements, anti-patterns, false-positive policy, and explicit lane boundaries against existing agents.

### New skills (3)

- **`/ultraprompt:test-gap-analysis`** — dispatches `test-gap-analyst`. Risk-weighted test gap identification with lane-based heuristic (auth/payment/data-deletion = critical; UI render = medium; admin = low).
- **`/ultraprompt:dead-code-drift`** — dispatches `dead-code-and-drift-hunter`. Produces drift_findings with safe_to_remove labels (yes/likely/needs_review/no) and migration plans.
- **`/ultraprompt:release-readiness`** — dispatches `release-readiness-auditor`. Returns ready/risky/blocked verdict with phased release sequence + gate criteria per phase.

### New persistent storage

- **`scripts/gap-ledger.py`** — gap-ledger writer/reader for `~/.ultraprompt/gaps/<repo>/gap-ledger.jsonl` (PRD §10.5).
  - Auto-generates sequential GAP IDs (GAP-<repo>-NNNN).
  - Subcommands: write, write-batch, list (with --status/--severity/--repo filters), update, path, stats.
  - Schema versioned (v: 1) for future migration.
  - Latest record per ID wins on read (append-only with logical updates).

### WIP snapshot fixture suite (PRD §8.1 fully satisfied)

10/10 fixtures passing in `tests/wip-snapshot/run-fixtures.py`:

| # | Acceptance criterion | Result |
|---|---|---|
| 1 | Staged tracked file captured | ✓ |
| 2 | Unstaged tracked file captured | ✓ |
| 3 | Untracked file captured | ✓ |
| 4 | Binary file captured | ✓ |
| 5 | Filename with spaces captured | ✓ |
| 6 | Nested directories captured | ✓ |
| 7 | Branch name collision: safe unique name | ✓ |
| 8 | Failure doesn't corrupt source worktree | ✓ |
| 9 | Source worktree restored exactly | ✓ |
| 10 | Snapshot verification reports passed | ✓ |

(Note: PRD §8.1 case 8 was "stash apply conflict" — N/A for V7 temp-worktree implementation; replaced with "failure doesn't corrupt source" which is the equivalent safety property.)

### Validators

- Schema audit (auto-detect): ✓ both runtimes
- Plugin validator: ✓ 0 errors, 0 warnings
- Duplication audit: ✓ 0 errors
- Skill tier audit: ✓ core 18 (alpha.3 added 3), specialist 15, ecosystem 5
- Drift audit: ✓ 0 errors
- Router bench: ✓ 100% top-3
- Hook fixtures: ✓ 26/26
- Destructive guard fixtures: ✓ 16/16
- WIP snapshot fixtures (NEW): ✓ 10/10

### Final counts

| | V6.6 | V7.0.0-alpha.3 | Δ |
|---|---|---|---|
| Agents | 9 | 17 | +8 (4 alpha.2 + 4 alpha.3) |
| Skills | 32 | 38 | +6 (1 alpha.1 + 2 alpha.2 + 3 alpha.3) |
| Commands | 20 | 21 | +1 (alpha.1) |
| MCP tools | 18 | 19 | +1 (alpha.1) |
| Hooks | 9 | 9 | 0 |
| Test fixtures | 26 | 52 | +26 (16 destructive + 10 WIP) |

### Deferred to alpha.4+

- **Mission Control state model** (PRD §9.2) — unified state.json reading repo capsule + worktree state + session lookup + evidence ledger + validation status + WIP snapshots + gap ledger. Requires the prior pieces (now mostly built) to integrate.
- **Evidence graph v3** (PRD §10.2) — provenance graph with claims/validations/artifacts links. Migration from ledger v2.
- **Auditor agents to write to gap-ledger automatically** — currently the auditors produce structured YAML; the user/orchestrator must write to gap-ledger. Full integration: skill body workflow includes `gap-ledger.py write` step.
- **Product/innovation/PRD/experiment families** (PRD §13, §17, §18) — separate slice. 24+ new agents, 40+ new skills.
- **Panel system as first-class** (PRD §21) — repo-completeness-panel, feature-gap-panel, contract-drift-panel, release-gate-panel. Currently the alpha.3 skills accept panel-style multi-agent dispatch but no formal panel-specs.json.
- **Artifact contracts validator** (PRD §28) — `artifact-validate` MCP tool + scripts.
- **Installer rollback hardening** (PRD §8.6) — install manifest tracking every file touched.

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically.

After install: start a NEW session for the V7.0.0-alpha.3 directive AND new agent descriptions to take effect together.

---

## [7.0.0-alpha.2] — 2026-05-10

V7 trust pack: closes PRD §8.1 Critical (verified WIP snapshot), expands repo-completeness from 1 to 4 agents (1/8 → 4/8 of the PRD §14 pack), upgrades destructive command guard to risk classifier (PRD §8.7), fixes the 3 doctor failures Eric flagged in Codex.

### Health-check fixes (Track A — fixed first)

| Failure | Fix |
|---|---|
| `dist/skill-index.json` stale | Rebuilt — current state |
| `.mcp.json` schema audit failure in Codex install | `audit-manifest-schemas.py` now auto-detects runtime from script path (`.codex` in path → codex rules). Doctor in either runtime no longer flags the other's `.mcp.json` |
| Duplication 25.3% over 10% budget | Standardized DISPATCH POLICY blocks extracted to `_shared/DISPATCH-POLICY.md`. Skill bodies now embed a single-line reference instead of the full template. Cross-skill share drops dramatically |
| Skill-tier count drift (core: 13, expected 12) | Expected count bumped to 15 for V7 (alpha.1 added `repo-review`; alpha.2 adds `gap-analysis` + `feature-completeness`) |

### Trust fixes (PRD Phase 0)

- **Verified WIP snapshot** (PRD §8.1, listed Critical) — temp-worktree implementation. Creates `git worktree add --detach` from HEAD, copies dirty files (staged + unstaged + untracked per policy, including binary, nested, spaces-in-filenames), commits via `git add -A`, verifies content hashes on sample, removes temp worktree. Original worktree never modified. Branch survives.
  - **`--legacy` fallback flag** retained (V6 stash-based path) as safety net per Option A recommendation. Default is V7 verified path.
  - **Auto-wip-save hook** updated to try V7 first; if V7 fails (returncode != 0), retries with `--legacy` automatically. Logs `verified` vs `legacy-fallback` badge in systemMessage.
- **Destructive command guard risk classifier** (PRD §8.7) — 4 classes (LOW/MEDIUM/HIGH/CRITICAL) with explicit overrides:
  - LOW (read-only, status) → allow silently
  - MEDIUM (`rm <file>`, `git stash drop`, `npm uninstall`, `DELETE FROM`) → warn via stderr, log to ledger, allow
  - HIGH (`rm -rf <target>`, `git reset --hard`, `git push --force`, `git clean -fdx`, `find -delete`, `DROP DATABASE`) → block; `ULTRAPROMPT_ALLOW_HIGH_RISK=1` per-session override available
  - CRITICAL (`rm -rf /`, `rm -rf ~`, `curl ... | bash`, fork bombs, sudo at root, credentials reads) → block unconditionally; no override
  - All classifications logged to V6 ledger as `destructive_guard_classification` events for audit
  - 16/16 smoke test fixtures pass

### New (V7 repo-completeness pack, 4/8 complete)

- **`ultraprompt:feature-completeness-auditor` agent** (PRD §14.2) — single-feature end-to-end auditor. Detects UI-without-backend, backend-without-UI, feature flags with no complete path, docs claiming features that don't exist, tests implying behavior the app doesn't implement, TODO/placeholder-driven incompleteness, etc. Produces structured `incomplete_features` entries.
- **`ultraprompt:wiring-gap-inspector` agent** (PRD §14.3) — repo-wide orphan-producer scan. Detects unmounted routes, uncalled API clients, orphan ORM models, declared-but-unenforced permissions, env vars read without docs, workers without queues, emitted events without listeners. Produces structured `wiring_gaps` entries.
- **`ultraprompt:gap-analysis-lead` agent** (PRD §14.8) — synthesis specialist. Merges findings from feature-completeness-auditor, wiring-gap-inspector, and (when available) test-gap-analyst, dead-code-and-drift-hunter. Dedupes, reconciles severity, separates confirmed from probable, produces ordered implementation sequence with recommended fix-skills per gap. Produces `repo_gap_report`.
- **`/ultraprompt:gap-analysis` skill** (PRD §19) — dispatches `gap-analysis-lead`. Multi-agent gap analysis with prioritized synthesis output.
- **`/ultraprompt:feature-completeness` skill** (PRD §19) — dispatches `feature-completeness-auditor`. Single-feature end-to-end audit.

### Architecture

- **`_shared/DISPATCH-POLICY.md`** — canonical V7 dispatch policy reference (single source). All dispatch-enabled skill bodies reference it instead of embedding identical template prose. Eliminates the 25.3% duplication.
- **Audit script runtime auto-detection** — `audit-manifest-schemas.py` checks its own path; if `.codex` is in the path, uses Codex rules by default. Manual `--runtime` override still works.

### Preserved from alpha.1

All V6 + alpha.1 carries forward: 9 prior agents + 1 (repo-cartographer) + 3 (alpha.2) = 13 total. 32 prior skills + 1 (repo-review) + 2 (alpha.2) = 35 total. 21 prior commands + 0 new = 21 (gap-analysis and feature-completeness exposed via skill auto-discovery; no new slash commands this release). 19 MCP tools unchanged. Telemetry hook (Agent matcher), V7 dispatch directive, release scorecard, drift audit, native Codex manifest, env override parser — all retained.

### Validators

- Schema audit (auto-detect): ✓ Claude-Code OK, Codex OK
- Plugin validator: ✓ 0 errors, 0 warnings
- Duplication audit: ✓ 0 errors (was 1 ERROR + 25.3% over budget; now within budget)
- Skill tier audit: ✓ 0 errors, 0 warnings
- Drift audit: ✓ 0 errors, 0 warnings
- Router bench: ✓ 100% top-3
- Hook fixtures: ✓ 26/26
- Destructive guard fixtures (NEW): ✓ 16/16
- MCP self-test: ✓ 19 tools
- Verified WIP snapshot smoke test: ✓ binary, spaces, nested, untracked, modified all captured with hash verification

### Deferred to alpha.3+ per PRD scope

- Remaining 4 repo-completeness agents (`integration-contract-reviewer`, `test-gap-analyst`, `dead-code-and-drift-hunter`, `release-readiness-auditor`) — each needs output contract + golden tests
- Mission Control state model (PRD §9.2)
- Evidence graph v3 (PRD §10.2)
- WIP snapshot full PRD §8.1 fixture suite (10 acceptance criteria — V7 alpha.2 covers 6 of 10; remaining: branch name collision verified, stash apply conflict N/A for temp-worktree impl, content-hash verification on ALL files not just sample, snapshot restoration test, ignored-policy variants)
- Installer rollback hardening (PRD §8.6) — install manifest tracking
- Product/innovation/PRD/experiment families — separate slice, lands after repo-completeness fully proves out
- Panel system as first-class — coordinated with artifact contracts in alpha.4
- Gap-ledger persistent writer to `.ultraprompt/gaps/gap-ledger.jsonl` — alpha.3 with full evidence graph

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically.

After install: start a NEW session for V7.0.0-alpha.2's directive AND regenerated skill bodies AND new agent descriptions to take effect together.

### What to test after install

| Test | Expected |
|---|---|
| `/ultraprompt:feature-completeness "auth flow"` | Dispatches `feature-completeness-auditor` with focus from $ARGUMENTS |
| `/ultraprompt:gap-analysis` | Dispatches `gap-analysis-lead` for synthesis |
| `/ultraprompt:repo-review` (alpha.1) | Now recommends gap-analysis-lead as followup dispatcher |
| Doctor in Codex | All 16+ checks pass (no more 3 failing) |
| Auto-WIP-save | systemMessage now ends with `(verified)` for V7 path or `(legacy-fallback)` for fallback |

---

## [7.0.0-alpha.1] — 2026-05-10

**V7 foundation release.** Lands PRD Phase 0 trust fixes plus the first repo-completeness skill/agent as proof-of-concept for the V7 product direction (PRD ultraprompt_v7_prd.md). Full V7 catalog (70-85 skills, 30+ new agents, panels, evidence graph, Mission Control state model) lands across subsequent alpha/beta releases per PRD §31 phased Implementation Plan.

### Why alpha

The V7 PRD (2552 lines) scopes a multi-week build with phased delivery: Phase 0 trust fixes, Phase 1 schema upgrade, Phase 2 Mission Control + evidence graph, Phase 3 repo-completeness pack (8 agents), Phase 4 product/innovation/PRD/experiment pack (24+ agents, 40+ skills, 7 panels, 9 commands), Phase 5 router/catalog governance, Phase 6 runtime-native packaging. PRD §35 explicitly lists "Release delayed by scope expansion" as a HIGH risk with mitigation: "Phase rollout; ship trust fixes and repo pack first if needed."

V7.0.0-alpha.1 is that staged delivery. It is production-installable, drop-in compatible with V6.6, and signals the V7 direction without overpromising.

### Trust fixes (PRD Phase 0)

- **Native Codex manifest source** (PRD §8.3) — `.codex-plugin/plugin.json` now committed as separate source, not synthesized by installer at install time. Codex-specific fields: runtime.codex_version_min, runtime.subagents_supported, capabilities.skills/mcp/hooks/subagents, compatibility_notes.
- **Env override double-underscore parser** (PRD §8.2) — `ULTRAPROMPT__SECTION__KEY=value` syntax for unambiguous nested overrides. Legacy single-underscore syntax emits deprecation warning; `ULTRAPROMPT_DISABLE_HOOKS` retains flat key parsing.
- **Drift audit script** (PRD §8.4) — `scripts/audit-drift.py` checks manifest counts vs actual artifacts, stale V5/V6 version references in current-state files, MCP tool count consistency. V7.0.0-alpha.1 ships with 0 drift errors and 0 warnings.

### New (V7 direction proof-of-concept)

- **`ultraprompt:repo-cartographer` agent** (PRD §14.1) — structured repo-mapping specialist that produces machine-readable YAML/JSON map (entrypoints, routes, data models, jobs, feature flags, test commands, deploy surfaces, risky areas, unknowns) for downstream review agent consumption. Wins over Explore and scout when consumer is another agent rather than a human reader.
- **`/ultraprompt:repo-review` skill + slash command** (PRD §19) — whole-repo audit dispatching cartographer for analysis phase. Produces structured repo_review_report artifact (executive summary, confirmed/probable gaps, test gaps, contract gaps, stale code, release readiness, top risks, quick wins, recommended sequence). For deep specialist passes (security-auditor, test-strategist, etc.), recommends dispatch but does not auto-chain.
- **`release_scorecard` MCP tool** (PRD §32.5) — plugin release-readiness check across manifest validity, discovery counts, routing accuracy, safety hooks, docs drift. Returns conclusion: ready / risky / blocked.
- **`scripts/release-scorecard.py`** — same scorecard via CLI. Used by doctor and CI.

### Preserved from V6.6

All V6 architecture and content carries forward unchanged:
- 32 prior skills (all V6.6 sharpened descriptions intact) + 1 new = 33 total
- 9 prior agents (all V6.5 sharpened) + 1 new = 10 total
- 20 prior commands + 1 new = 21 total
- 18 prior MCP tools + 1 new = 19 total
- All hooks (telemetry, guards, auto-WIP-save, SessionStart, Stop, SessionEnd) unchanged
- Skill auto-discovery, dispatch-first architecture, multi-session safety, evidence ledger v2, claim_check / dispatch_advise / route_intent — all intact

### Validators

- Schema audit: ✓ 0 errors (claude-code, codex)
- Plugin validator: ✓ 0 errors, 0 warnings
- Router bench (positive): ✓ 48/49 top-1 (98%), 49/49 top-3 (100%)
- Router bench (adversarial): ✓ 12/12 rejected
- Hook fixtures: ✓ 26/26
- MCP self-test: ✓ 19 tools
- Drift audit: ✓ 0 stale refs
- Release scorecard: ✓ READY

### Explicitly deferred to V7.0.0-alpha.2+ per PRD scope

- **Verified WIP snapshot** (PRD §8.1, listed Critical) — temp-worktree implementation, content hash verification, restore-on-failure. Real surgery; needs full test fixture suite.
- **Mission Control state model** (PRD §9.2) — unified state.json reading repo capsule + worktree state + session lookup + evidence ledger + validation status + WIP snapshots + gap ledger.
- **Evidence graph v3** (PRD §10.2) — provenance graph with claims/validations/artifacts/derived-from links.
- **Destructive command guard risk classes** (PRD §8.7) — Low/Medium/High/Critical classifier.
- **Installer rollback hardening** (PRD §8.6) — install manifest tracking every file touched.
- **Repo-completeness agent pack** (PRD §14) — feature-completeness-auditor, wiring-gap-inspector, integration-contract-reviewer, test-gap-analyst, dead-code-and-drift-hunter, release-readiness-auditor, gap-analysis-lead.
- **Product/innovation/PRD/experiment agents and skills** (PRD §13, §17, §18) — 24+ new agents, 40+ new skills across 4 families.
- **Panel system as first-class** (PRD §21) — idea-panel, prd-panel, experiment-panel, mvp-panel, ai-feature-panel, enterprise-feature-panel, iteration-panel + repo-completeness-panel, feature-gap-panel, contract-drift-panel, release-gate-panel.
- **Artifact contracts** (PRD §28) — PRD, concept brief, opportunity map, experiment plan, metric tree, decision memo, gap ledger, repo review report, release scorecard, ADR, validation plan, evidence proof card.

### Migration

Drop-in via `scripts/install.sh both`. No config changes required. Existing ledger continues; backups created automatically. After install: start a NEW session for V7 directive to take effect.

### V7 north star (PRD §48)

> Ultraprompt should not only help the user code. It should help the user discover what to build, specify it clearly, test the idea, implement it safely, audit the repo for gaps, and prove what was validated.

V7.0.0-alpha.1 lands the foundation (trust + repo-cartographer + repo-review + release-scorecard). The rest of V7 lands incrementally.

---

## [6.6.0] — 2026-05-09

V6.6 closes the outcome-telemetry gap that V6.5 surfaced. Pure observability work — no architectural change, no description changes, no skill or agent additions.

### Why

V6.5 telemetry could answer "did dispatches happen?" but not "did they produce value?". Specifically:
- claim_check fired 12 times in 7 days but we couldn't see if any failed (the discipline value is in rejections, not pass-throughs)
- dispatch_advise had 0 organic adoption with no way to measure if recommendations were being followed when called
- route_intent fired but the suggested skill wasn't logged

V6.6 patches the MCP server's `_ledger_write_call` to extract outcome fields from each tool's result and write them into the `mcp_tool_call` event.

### Added

- **Outcome fields in `mcp_tool_call` events**:
  - `claim_check` → `passed` (bool), `check_count` (int), `fail_count` (int)
  - `dispatch_advise` → `recommend` ('inline'|'dispatch'), `agent` (suggested ultraprompt:* agent), `top_skill`, `is_interactive`
  - `route_intent` → `top_skill` (suggested), `confidence`
- **`scripts/doctor-evidence-discipline.py`** — surfaces claim_check pass/fail ratio, dispatch_advise recommendation distribution, agents recommended.
- **Doctor command step 16** — calls the new evidence-discipline script.

### Changed

- `mcp/ultraprompt_meta.py`: `_ledger_write_call` accepts `extra` dict; new `_extract_outcome_fields` function inspects results before logging.
- Doctor command renumbered (16 → 17 for V6 ledger summary; new step 16 for evidence discipline).
- Version strings bumped to 6.6.0; SessionStart context tagged V6.6.

### What V6.6 will reveal

After 7 days of V6.6 telemetry:

| Question | Answered by |
|---|---|
| Is claim_check catching real false claims, or rubber-stamping? | `passed`/`fail_count` distribution |
| Is dispatch_advise being followed when called? | `recommend` field + correlation with subsequent `agent_dispatch` |
| Which agents does dispatch_advise actually recommend in real prompts? | `agent` distribution |
| Is route_intent's top suggestion well-calibrated? | `confidence` field + correlation with skill_invocation |

If after 7 days `claim_check.fail_count` is 0 across all calls, the discipline is being followed as theatre — useful as a forcing function, not as actual validation. That would inform V6.7 priority.

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing pre-V6.6 mcp_tool_call events remain in the ledger without outcome fields; new events have them. Doctor's evidence-discipline script handles both gracefully.

After install: **start a NEW session** for V6.6 to write outcome fields on subsequent tool calls.

---

## [6.5.0] — 2026-05-09

V6.5 closes activation gaps identified by V6.4 telemetry. No new architecture, no new MCP tools, no new skills — instead: sharper descriptions, better observability, and explicit anti-pattern callouts to win against built-in agents.

### What V6.4 telemetry showed

Inspecting `~/.claude/projects/<session>/subagents/` directly (subagents created in the V6.4 window):

- 12 subagent dispatches over ~2.5h
- 8 plugin specialist dispatches (debugger×7, reviewer×1) — V6.4 architecture working for analysis lanes
- 4 Explore dispatches for "Map X / Read Y" patterns — `ultraprompt:scout` lost every time
- 7 of 9 specialist agents never fired (auditor, security-auditor, scout, test-strategist, writer, adversarial, router)
- `agent_dispatch` ledger events: 0 — but the dispatches really happened. **Telemetry hook bug**: `tool_name="Agent"`, hook matched `"Task"`.

### Fixed

- **Telemetry hook now matches `Agent` tool** (the hook had matched `Task` and `Skill` only, missing every real subagent dispatch). One-line fix in `hooks/recipes/skill-agent-telemetry.py`. Closes the V6.3-shipped observability bug.

### Added

- **`scripts/doctor-dispatch-outcomes.py`** — independent observability path. Reads subagent JSONLs in `~/.claude/projects/<session>/subagents/` directly. Surfaces plugin vs Explore split, per-agent counts, never-fired specialists, recent dispatch timeline. Survives future telemetry hook bugs.

- **`scripts/doctor-skill-activation.py`** — per-skill auto-discovery scorecard. Reads V6 ledger v2. Surfaces never-fired skills with sharpening recommendation. Reports MCP tool adoption (claim_check, route_intent, dispatch_advise — flagged with ★).

- **Doctor command updated** to call both new scripts (steps 14-15). Final summary now reports plugin specialist dispatch share + never-fired specialists.

### Changed (aggressive description rewrites)

Goal: claim user-trigger phrasing that matches how prompts are actually written, win over built-in Explore for prompts that hit specialist lanes.

**7 agent descriptions rewritten** with explicit "USE WHEN user says: 'X', 'Y', 'Z'" patterns and "DEFAULT CHOICE" + "DO NOT use for" framing:

- `scout` — claims "map X / explore Y / show me how Z works / what's in package W / orient me to this codebase"
- `auditor` — claims "audit X for Y / sweep our code for Z / check our W for compliance"
- `security-auditor` — claims "audit auth / check for injection / review secrets / threat model"
- `test-strategist` — claims "find coverage gaps / design test cases / regression plan"
- `writer` — claims "draft release notes / write changelog / document this decision / create ADR"
- `adversarial` — claims "red-team this / devil's advocate / find the weakness / stress-test"
- `router` — claims "uncertain which skill to invoke for free-form intent" (defers to `route_intent` MCP tool for low-latency routing)

**14 skill descriptions sharpened** with "When user says X / Y / Z" leading phrasing: repo-map, test-harden, architect, api-contract, dependency-audit, supply-chain-hardening, accessibility-review, db-schema-review, infra-iac-review, observability-pass, data-flow-privacy-map, ai-agent-safety-review, cost-audit, performance-pass, state-machine-review.

**SessionStart context (V6.5)** with explicit anti-pattern callouts:
- "DO NOT dispatch built-in Explore for: 'map X / explore Y / show me Z' → use `ultraprompt:scout`"
- "DO NOT dispatch built-in Explore for: 'audit X for Y' → use `ultraprompt:auditor`"
- Each unfired specialist's territory explicitly claimed vs Explore

**MCP instructions (V6.5)** — `dispatch_advise` promoted to first slot. New rule: "FIRST CALL when uncertain: dispatch_advise. Returns dispatch-vs-inline recommendation. Cost: one MCP call. Benefit: prevents wrong-tool dispatches."

### Telemetry expectations (V6.4 → V6.5)

| Metric | V6.4 (real, 7d) | V6.5 expected |
|---|---|---|
| Plugin specialist dispatch share | 38% (10/26) | ≥ 60% target |
| `ultraprompt:scout` dispatches | 1 | ≥ 4 (scout was losing 16:1 to Explore) |
| Never-fired specialists | 5/9 (auditor, test-strategist, writer, adversarial, router) | ≤ 2/9 over 7d |
| `agent_dispatch` ledger events | 0 (broken) | matches subagent JSONL count |
| `dispatch_advise` MCP calls | 0 | > 0 organic adoption |
| `claim_check` MCP calls | 12/7d | continues |

If V6.5 doesn't move the scout share substantially, the issue is deeper than description quality — likely Claude Code's Explore is hard-coded as the discovery default and doesn't honor description-based override. Different intervention needed for V6.6.

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically.

After install: **start a NEW session** (not resume) for V6.5's directive AND the regenerated skill bodies AND the rewritten agent descriptions to take effect together.

---

## [6.4.0] — 2026-05-09

Architectural shift: **dispatch-first**. The 18 skills with corresponding specialist agents now dispatch by default, keeping main-thread context clean and using persona-locked specialists for stronger lane-specific reasoning.

### Why

V6.3 telemetry confirmed skill auto-discovery works (security-audit auto-fired correctly), but the work was executed inline in the main thread — pulling 8+ file reads, multiple grep results, validation runs, and the entire skill discipline into context. Subsequent turns inherit that pollution. The audit was good, but the cost was main-thread context budget.

V6.4 inverts the default: skills dispatch to specialists via Task. Specialist runs with clean context. Main thread receives synthesized report instead of working state.

### The dispatch trade-off

| Inline (V6.3 default) | Dispatch (V6.4 default) |
|---|---|
| Faster for trivial work | Better for consequential work |
| Main thread sees everything (fluid) | Main thread sees report (clean) |
| One context budget | Two context budgets (specialist + main) |
| Persona = generalist | Persona = specialist |
| Good for "what does X do?" | Good for "audit X" |

The new rule: **if work would take >5 file reads, dispatch. If trivial, inline.** Use `dispatch_advise` MCP tool when uncertain.

### Added

- **`dispatch_advise` MCP tool** — given user intent + estimated_files_to_read + is_interactive, returns dispatch-vs-inline recommendation with reasoning and Task brief skeleton. 18th MCP tool.
- **`dispatch_to` field in skill specs** — 18 skills mapped to specialist agents (with focus param where applicable). Drives the regenerated SKILL.md DISPATCH POLICY section.
- **DISPATCH POLICY section in SKILL.md** — for the 18 dispatch-friendly skills. Leads with explicit Task template. Inline override clearly documented.

### Changed

- **DISCIPLINE.md section 4** rewritten for V6.4 dispatch-first strategy. New rule: skills with specialist agents dispatch by default; inline only with explicit conditions.
- **SessionStart hook** updated to V6.4 — lists which skills dispatch and which stay inline. 3802 chars.
- **MCP instructions** updated to 1774 chars (under truncation limit). Highlights `dispatch_advise` first.
- **`scripts/regenerate-skills.py`** updated to inject DISPATCH POLICY block when `dispatch_to` is set in spec.
- **18 SKILL.md bodies regenerated** with V6.4 dispatch policy at the top of each.

### Skills that dispatch (V6.4)

| Skill | Agent | Focus |
|---|---|---|
| `review` | reviewer | from `$ARGUMENTS` |
| `security-audit` | security-auditor | — |
| `debug` | debugger | — |
| `architect` | reviewer | architecture |
| `api-contract` | reviewer | contract |
| `performance-pass` | reviewer | performance |
| `state-machine-review` | reviewer | code |
| `repo-map` | scout | — |
| `test-harden` | test-strategist | — |
| `dependency-audit` | auditor | dependencies |
| `supply-chain-hardening` | auditor | supply-chain |
| `accessibility-review` | auditor | a11y |
| `db-schema-review` | auditor | db |
| `infra-iac-review` | auditor | infra |
| `observability-pass` | auditor | observability |
| `data-flow-privacy-map` | auditor | privacy |
| `ai-agent-safety-review` | auditor | ai-safety |
| `cost-audit` | auditor | cost |
| `release` (analysis phase) | writer | — |
| `ci-repair` (analysis phase) | debugger | — |

### Skills that stay inline

`build`, `refactor`, `migrate`, `llm-eval-design`, `tui-design-innovate`, `contract-test-generate` — interactive by design; user iterates step-by-step. Skill bodies omit DISPATCH POLICY section.

### Telemetry expectations

| Metric | V6.3 (last 24h) | V6.4 expected |
|---|---|---|
| `agent_dispatch` events with `is_plugin_agent=true` | 0 | should rise as auto-discovered skills dispatch |
| `skill_invocation` events | non-zero | continues |
| Main-thread context size after audit | bloated | clean (just synthesis report) |

If after 24h `agent_dispatch` for `ultraprompt:*` agents is still 0, the V6.4 directive isn't producing behavior change beyond V6.3 — would mean Claude is actively choosing inline despite skill body's DISPATCH POLICY directive.

### Migration

Drop-in via `scripts/install.sh both`. No config changes. Existing ledger continues; backups created automatically.

After install: **start a NEW Claude Code / Codex session** (not resume) for V6.4's directive to take effect. Subsequent resumes will fire the V6.4 hook on every reload.

---

## [6.3.0] — 2026-05-09

Telemetry from V6.2 confirmed skill auto-discovery works (2/2 directed prompts auto-fired correct skills) but identified two remaining gaps: plugin specialist agents not auto-dispatching (Claude Code's built-in `Explore` picks up the work instead), and `skill_invocation` / `agent_dispatch` events not wired in the V6 ledger schema. V6.3 closes both.

### Added

- **Specialist agent dispatch routing** in `session-start-context.sh`. For each of the 9 specialist agents (`reviewer`, `auditor`, `security-auditor`, `debugger`, `scout`, `test-strategist`, `writer`, `adversarial`, `router`), the SessionStart directive now includes a "BEFORE dispatching `Explore` for X → dispatch `ultraprompt:Y`" pattern. Same architectural pattern as V6.2's skill routing — hooks deliver, not MCP instructions, so resume-heavy use sees fresh content.

- **Skill + agent dispatch telemetry hook** (`hooks/recipes/skill-agent-telemetry.py`). PreToolUse hook with no matcher; observes when Claude calls `Skill` or `Task` tools. Filters for `ultraprompt:*` identifiers. Writes `skill_invocation` or `agent_dispatch` events to the V6 ledger. Passive observer — never blocks, always exits 0. Closes the observability gap that prevented measuring V6.2's auto-discovery rate.

- **`route_decision` events from `route_intent` MCP tool**. When the routing tool returns a top-3, it now logs the intent + suggested skill + confidence to the ledger. Future analysis can correlate `route_decision` events against subsequent `skill_invocation` events to compute routing accuracy in real usage.

- **Doctor reads V6 ledger v2**. The `/ultraprompt:doctor` command now reports both V5 evidence-ledger (back-compat) and V6 ledger v2 (canonical V6.3 source). New summary section surfaces auto-discovery rate, MCP tool usage, and auto-WIP-save activity.

### Changed

- `commands/repo-capsule.md` description sharpened to lead with user-trigger phrasing ("When entering an unfamiliar repo or starting cross-cutting work...").
- `mcp/ultraprompt_meta.py` version bumped to 6.3.0; `route_intent` tool now writes ledger events.
- `hooks/hooks.json` registers the new telemetry hook on PreToolUse.

### V6.2 → V6.3 telemetry expectations

After V6.3 is live in a fresh session for ~30 minutes of active work:

| Metric | V6.2 baseline (3h) | V6.3 expected (30min after fresh session) |
|---|---|---|
| `skill_invocation` events | not wired | should be > 0 if V6.2's directive holds |
| `agent_dispatch` events | not wired | should be > 0 specifically for `ultraprompt:*` agents |
| `mcp_tool_call` events | 1 organic | should grow incrementally |
| `wip_save` events | 14 in 3h | should continue at similar rate |

If `skill_invocation` for `ultraprompt:*` skills shows 0 after 30 min of active work, V6.3's directive isn't producing behavior change beyond V6.2 — different intervention needed (likely description rewrites for the specific patterns Eric uses most).

### Migration from V6.2

Drop-in install via `scripts/install.sh both`. No config changes. Existing ledger continues; user TOML preserved; backups created automatically.

After install: **start a NEW Claude Code session** (not resume) for the V6.3 directive to take effect. Subsequent resumes will then fire the V6.3 hook on every reload.

---

## [6.2.0] — 2026-05-09

Architectural fix for resume-heavy session use. V6.1.1 telemetry showed that long-running sessions (Eric: 27h continuous on Celestial) don't pick up MCP `instructions` field updates even after Claude Code restart, because session resume replays cached `mcp_instructions_delta` attachments from the transcript instead of re-fetching from the server.

### Added

- **Routing directive baked into `session-start-context.sh` hook output** (2805 chars). Hooks re-execute on every session start AND every resume — unlike MCP `instructions` which is cached at server-connection time and replayed from transcript. This makes plugin updates reliably take effect for users with resume-heavy patterns.

### Architectural change

V6.0 → V6.1: tried to use MCP `instructions` field as the routing channel. Worked for fresh sessions, failed for resumed sessions.

V6.2: SessionStart hook is now the canonical channel for routing guidance. MCP `instructions` field still exists as a backup (and serves fresh sessions), but the SessionStart hook contains the full directive — covering the same content the MCP block does, plus more concrete BEFORE patterns.

### Why this design

| Channel | Re-executes on plugin update? | Survives session resume? |
|---|---|---|
| Hook scripts | ✓ (re-spawned each fire) | ✓ (re-fires on every session start) |
| MCP `instructions` | ✓ (server reconnects) | ✗ (transcript caches the old delta) |
| Skill listing | ✗ (cached at session init) | ✗ |
| CLAUDE.md content | ✓ (re-read each session) | ✗ (cached as system context) |

Hooks are the only deterministic re-execution channel. V6.2 leans on that fact.

### Migration from V6.1.x

Drop-in install. No config changes. Existing ledger continues; user TOML preserved; backups created automatically.

After install: **start a NEW session (don't resume)** to validate V6.2's directive lands properly. Subsequent resumes will then fire the V6.2 hook on every reload, keeping routing guidance fresh.

---

## [6.1.0] — 2026-05-09

Diagnostic-driven release. Telemetry from V6.0 (deployed 2026-05-08) showed zero `mcp_tool_call` and zero `skill_invocation` events in 16 hours of active sessions despite 15 sessions started. Plugin was technically loaded but contextually invisible.

### Added

- **MCP `instructions` block in initialize response**. The single biggest unlock. Mirrors the structure other MCP servers (`computer-use`, `Figma`) use to inject decision-pattern guidance into every Claude Code session. 3.4KB of "use route_intent when unsure", "use claim_check before final answers", "use repo_capsule on unfamiliar repos", "use worktree_state on multi-session confusion." Without this, Claude saw 17 tools but no signal about when to reach for them.
- **`mcp_tool_call` telemetry**. Every tool call now writes a ledger event (`{ts, tool, args, dur_ms, ok}`). V6.x priorities can now be evidence-driven instead of synthesized.

### Changed

- **`session-start-context.sh` updated from V5 to V6.1**. Was still announcing "Ultraprompt V5 is active" in every session. Now lists actual V6.1 decision points (route_intent, repo_capsule, claim_check, status, debug, build, etc.) with concrete trigger phrasing.
- **5 skill descriptions rewritten** to lead with user trigger phrases rather than abstract category names: `state-machine-review`, `performance-pass`, `observability-pass`, `data-flow-privacy-map`, `infra-iac-review`. Each now starts with "When the user mentions..." or "When the user describes..." to match Claude's auto-discovery matcher.
- **`panel-run` command description rewritten**. Was "Multi-perspective parallel review using a pre-baked panel pattern" — purely abstract. Now leads with concrete trigger conditions ("cross-cutting diffs, complex bugs with multiple plausible causes...").

### Fixed (carried from V6.0.x patches)

- `auto-wip-save.py` Stop hook output uses top-level `systemMessage` instead of `hookSpecificOutput.additionalContext` (Stop hooks don't accept hookSpecificOutput per Claude Code schema).
- `session-finalize.py` SessionEnd hook same fix.
- `audit-manifest-schemas.py` is runtime-aware via `--runtime` flag (claude-code default; codex when invoked from Codex installer).

### Why this matters

V6.0 deployed and looked fine on validators (32 skills enumerated, 17 tools registered, hooks fired). But real-world telemetry showed Claude's invocation rate of plugin features was zero. The diagnosis: tools were technically present but contextually invisible. Other MCP servers in the same sessions (`computer-use`, etc.) get rich `mcp_instructions_delta` blocks; ours was empty. V6.1 fixes the contextual-visibility gap. Future versions will use the new `mcp_tool_call` telemetry to validate this fix is actually moving the needle.

### Migration from V6.0

Drop-in install via the bundled scripts. No config changes required. Existing ledger continues; user TOML preserved; backups created automatically.

---

## [6.0.0] — 2026-05-08

Major release: multi-session/worktree-aware safety net + observability foundation + V5 bug fixes.

### Added — Tier 0 (multi-session safety)

- `/ultraprompt:status` — cross-worktree dashboard with urgency triage (CRITICAL / NEEDS TRIAGE / IN FLIGHT / WATCH / CLEAN). Detects active sessions, dirty counts, unpushed commits, in-progress operations, stale worktrees.
- `/ultraprompt:wip-save` — atomic snapshot of dirty state to `wip/<repo>/<worktree>/<utc-timestamp>` branch via stash+branch+pop pattern. Refuses on in-progress merge/rebase/cherry-pick. Optional push to backup remote.
- `/ultraprompt:wip-prune` — list/delete WIP branches by retention threshold.
- `/ultraprompt:resume` — synthesizes "where was I" from prior session JSONL + WIP branches + current state.
- `/ultraprompt:checkpoint` — manual ledger checkpoint snapshot.
- `/ultraprompt:cleanup` — triage-by-grouping for dirty trees (path, file type, magnitude).
- `/ultraprompt:new-worktree` — wrapper around `git worktree add` with ledger intent recording.
- `/ultraprompt:install-monitor`, `:uninstall-monitor`, `:monitor-status` — manage the launchd-driven worktree monitor.
- `/ultraprompt:usage` — real plugin usage analytics from ledger v2 (replaces V5 stub).

### Added — Tier 1 (observability foundation)

- Always-on evidence ledger v2 at `~/.claude/ultraprompt-data/events-YYYY-MM.jsonl`. Schema-versioned (v2). Append-only. Monthly rotation. Documented event types.
- `~/.claude/ultraprompt.toml` configuration surface with sensible ADHD-protective defaults. Layered (defaults → user → project → env vars).
- 4 new MCP tools: `worktree_state`, `session_lookup`, `ledger_query`, `wip_save_advise` (total 17, up from 13).

### Added — Tier 1 (between-session autonomy)

- `worktree-monitor.py` launchd-driven scanner. Two agents: every-30-min scan + daily 9 AM digest.
- macOS Notification Center integration with quiet-hours config.
- Auto-WIP-save trigger from monitor (when threshold crossed and cooldown expired).

### Added — V6 hooks (in-session autonomy)

- `session-bootstrap.py` (SessionStart): worktree-state snapshot to ledger + bootstrap banner if warnings apply (dirty above threshold, unpushed, concurrent session, in-progress operation).
- `auto-wip-save.py` (Stop): auto-WIP-save when dirty growth exceeds threshold and cooldown elapsed.
- `session-finalize.py` (SessionEnd): diff-against-checkpoint final report + ledger session_end event.

### Added — V5 lessons (must-have fixes)

- `audit-manifest-schemas.py`: catches the V5 bug class (`cwd` field rejected by Claude Code, missing `mcpServers` declaration in manifest, unknown fields).
- Per-runtime `.mcp.json`: `.mcp.json` (Claude Code: `${CLAUDE_PLUGIN_ROOT}` env-var path) + `.codex.mcp.json` (Codex: relative path + `cwd: "."`). Install scripts pick the right one per runtime.
- Plugin manifest now includes `"mcpServers": "./.mcp.json"` field (required for Codex; recommended for Claude Code).
- Dual-runtime install scripts: `install-claude-code.sh`, `install-codex.sh`, unified `install.sh both`.
- Codex install scripts handle the dual-folder pattern (`.claude-plugin/` + `.codex-plugin/`) and the cache-refresh dance automatically.

### Changed

- `mcp/ultraprompt_meta.py` version bumped to 6.0.0.
- `hooks/hooks.json` updated with new V6 hooks; V5 hooks preserved.
- `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` routing additions documented.

### Deferred to V6.1

- Cleanup heuristic ML-style intent grouping (V6.0 ships path/size/age clustering).
- Calibrated claim-check fixture corpus + bench.
- Real /usage dashboard rich analytics (V6.0 ships basic ledger summary).
- 5-skill quality pass on uneven lanes (tui-design-innovate, state-machine-review, llm-eval-design, ai-agent-safety-review, migrate).

### Migration from V5

The install scripts handle migration automatically:
- Existing V5 plugin → backed up to `~/.claude/backups/ultraprompt-pre-v6-<timestamp>/`
- V5 `.mcp.json` bug fixes applied (`cwd` field removed, `mcpServers` declaration added)
- Codex stale cache moved aside, forcing fresh re-cache from source
- User config (if exists) preserved; new defaults added

## [5.0.0] — 2026-05-07

(Previous release; see CHANGELOG history for details.)
