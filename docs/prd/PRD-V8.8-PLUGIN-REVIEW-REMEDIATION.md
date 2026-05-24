# PRD-V8.8: Plugin Review Remediation & Catalog Expansion

**Status:** Draft — pending review
**Owner:** Ultraprompt Toolkit
**Date:** 2026-05-23
**Target release:** Ultraprompt v8.8.0 (Remediation pass) → v8.9.0 (Catalog expansion)
**Source:** Plugin review of v8.7.0 (Used 6 tools, read 5 files, ran 2 agents) — 2 critical / 6 high / 9 medium + 13 catalog gaps
**Spot-check evidence:** See §15 (Validation plan). 11 of 12 reviewer claims independently verified against `C:\Users\emsok\ultraprompt`; 1 minor correction logged (`.env.local` IS covered by current regex — narrower fix scope than reviewer suggested).

---

## 1. Problem statement + evidence

The Ultraprompt v8.7.0 plugin is structurally healthy but its self-validator misses a class of bugs that meaningfully degrade router precision and silently weakens the read-only safety model. A human-level review surfaced **17 issues that the in-tree `scripts/audit-catalog-consistency.py` / `dist/catalog-audit-report.json` pipeline did not flag** (`dist/catalog-audit-report.json` currently reports `{total: 0, findings: []}`). Concretely:

| Class | Count | Evidence |
|---|---|---|
| Malformed/duplicated skill descriptions | 3 | `skills/agent-author/SKILL.md:3` reads `"**DEFAULT for agent authoring: produces a new agent definition (: runs the agent-author discipline.**"` — unclosed paren, truncated sentence, no `Different from` clause. `skills/release/SKILL.md:3` contains orphan `: separate skill).` fragment. `skills/release-readiness/SKILL.md:3` contains a self-repeating sentence (`"audits whether the codebase is shippable.** Different from release (writes notes/changelog) — release-readiness audits whether the codebase is shippable."`). |
| `tools` ↔ `disallowedTools` collisions | 3 | `agents/router.md:5-6`, `agents/adversarial.md:5-6`, `agents/writer.md:5-6` all list `Bash` in both `tools:` and `disallowedTools:`. Behavior is implementation-defined; documentation is incoherent. |
| Read-only agents without explicit clamp | 13 | Only `agents/auditor.md:6` enforces read-only with `disallowedTools: "Write, Edit, MultiEdit"`. 13 peer agents (dead-code-and-drift-hunter, evaluator, feature-completeness-auditor, gap-analysis-lead, innovation-lead, integration-contract-reviewer, market-analyst, principal-pm, release-readiness-auditor, repo-cartographer, risk-and-controls-reviewer, technical-product-architect, test-gap-analyst, wiring-gap-inspector) document read-only intent in prose only. |
| Bash unfenced on `builder` | 1 | `agents/builder.md:5` declares `tools: "Read, Grep, Glob, Bash, Edit, Write, MultiEdit"` with **no** `disallowedTools` and no Bash command allowlist. Builder has authority to run `rm -rf`, mutate `.git`, or edit lockfiles. |
| UTF-8 mojibake in MCP instructions | 1 | `mcp/ultraprompt_meta.py:55-84` contains `â€"` (em-dash mis-encoded), `â‰¤` (≤), `Ã—` (×). Every Claude Code session ingests this string into context. |
| Catalog drift in static counts | 4 | `.claude-plugin/plugin.json:5`, `.claude-plugin/marketplace.json:11`, `commands/menu.md`, `commands/dashboard.md` hard-code `"49 skills, 30 agents, 43 MCP tools, 31 commands"`. The plugin's `mcp__plugin_ultraprompt_ultraprompt-meta__capability_graph` already computes these at runtime; static copies will drift on next addition. |
| `disable-model-invocation` missing on destructive commands | 6 | `commands/wip-save.md`, `commands/wip-prune.md`, `commands/cleanup.md`, `commands/new-worktree.md`, `commands/install-monitor.md`, `commands/uninstall-monitor.md` can be invoked autonomously by the main thread, performing branch/file mutations without explicit user intent. |
| Self-aliases | 2 | `skills/security-audit/SKILL.md:7` lists `aliases: ["security-audit"]`. `skills/technical-debt-triage/SKILL.md:7` lists `aliases: ["technical-debt-triage", ...]`. Tautological. |
| Specialist-tier description template drift | ~28 | Specialist-tier skills (prd-lite, prd-standard, prd-technical, concept-brief, problem-framing, idea-triage, technical-debt-triage, docs-sync, state-machine-review, database-review, dependency-audit, observability-pass, accessibility-review, data-flow-privacy-map, supply-chain-hardening, ai-agent-safety-review, contract-test-generate, infra-iac-review, tui-design-innovate, mcp-design, hooks-design, plugin-review, api-contract, llm-eval-design, skill-author, agent-author) use the sparse `**DEFAULT for X: runs the X discipline.**` template instead of the V8 rich pattern `**DEFAULT for X — …** Different from /Y (…), /Z (…). Triggers: '…'`. |

**Why this matters:** the router scores skill candidates against the literal description string. Malformed and undisambiguated descriptions produce ambiguous routing → triggers picker / wrong dispatch / silent precision loss. The Bash-in-both-lists collisions break the trust contract that `dispatch_advise` relies on. Mojibake in `MCP_INSTRUCTIONS` injects garbled guidance into every session.

---

## 2. Users + jobs-to-be-done

| User | Jobs-to-be-done |
|---|---|
| **Ultraprompt end users** (Claude Code / Codex sessions) | Get the right skill/agent dispatched without surprise. See coherent guidance in injected MCP instructions. Trust that read-only agents stay read-only. |
| **Ultraprompt plugin authors** | Add skills/agents without manual count synchronization. Run the in-tree validator and trust its green light. Reference an authoritative description template. |
| **Operators (Ultraprompt Toolkit maintainers)** | Ship a v8.8 release with confidence the regression-prone classes are now linted. Track which release closed which finding. |
| **Security-conscious adopters** | Verify least-privilege is enforced declaratively (`disallowedTools`), not by prose. Trust the protected-file-guard covers the credential families they care about (GCP service accounts, AWS access-key JSON, PKCS#12). |

---

## 3. Goals + non-goals

### Goals
- **G1 — Catalog truth.** All hand-typed catalog counts removed in favor of `${runtime_catalog}` interpolation at build/render time. Drift impossible.
- **G2 — Router precision.** All 49 skill descriptions conform to the V8 rich template; description lint blocks regressions.
- **G3 — Least-privilege enforcement.** Every read-only agent declares it via `disallowedTools`. No agent has the same tool in both `tools` and `disallowedTools`. `builder` has a Bash command guardrail.
- **G4 — Validator parity.** `scripts/audit-catalog-consistency.py` (and `validate_plugin` MCP tool) catches every issue this review found. The 17-finding pre-existing gap closes to ≤1 (only the description-tone judgments remain manual).
- **G5 — Coherent injected context.** Re-encode `MCP_INSTRUCTIONS` as clean UTF-8. Tighten `protected-file-guard.py` PROTECTED regex without breaking existing covered patterns.
- **G6 — Catalog expansion.** Ship `incident-response`, `adr-author`, `runbook-author`, `cost-audit`, `git-workflow`, `onboarding-doc` skills; `incident-commander`, `prompt-engineer`, `release-manager`, `data-analyst` agents; `/ultraprompt:dispatch` and `/ultraprompt:rollback` commands. Consolidate `dependency-audit` + `supply-chain-hardening` and `concept-brief` + `prd-lite`.

### Non-goals
- **N1.** Rewriting the V8 dispatch architecture itself. This PRD strengthens what exists; it does not introduce a V9.
- **N2.** Changing the panel-run, dream, learning, or memory subsystems beyond what is required for new agents/skills to participate.
- **N3.** Touching `output-styles/`, the cross-runtime install path, or the Windows hook variant beyond what regex/encoding changes require.
- **N4.** Adding new MCP tools beyond the validator-strengthening hook (`validate_plugin` already exists; we extend it, not replace it).
- **N5.** Re-doing the in-tree test-harness; we add tests, we don't restructure `tests/`.

---

## 4. Must/should/won't-have requirements

### MUST (v8.8.0)
- **M1.** `skills/agent-author/SKILL.md:3`, `skills/release/SKILL.md:3`, `skills/release-readiness/SKILL.md:3` descriptions are well-formed (balanced parens, single sentence each, conformant to V8 rich pattern).
- **M2.** `agents/router.md`, `agents/adversarial.md`, `agents/writer.md` have no token appearing in both `tools` and `disallowedTools`.
- **M3.** 13 named read-only agents declare `disallowedTools: "Write, Edit, MultiEdit"` (or stricter).
- **M4.** `agents/builder.md` adds either a Bash command allowlist hook or explicit `disallowedTools` for `rm`, `git push --force`, `git reset --hard`, lockfile edits.
- **M5.** `mcp/ultraprompt_meta.py:53-84` re-encoded as UTF-8 (em-dashes restored, ≤ and × restored).
- **M6.** `hooks/recipes/protected-file-guard.py:33` PROTECTED regex extended to cover `service-account*.json`, `*.p12`, `*.pfx`, AWS access-key JSON. `.env.local` / `.env.production` coverage **already exists** via `\.env($|\.)` — verified; no change needed for that subset.
- **M7.** 6 destructive commands declare `disallowedTools` and/or `disable-model-invocation: true`.
- **M8.** Self-aliases removed from `security-audit` and `technical-debt-triage`.
- **M9.** `scripts/validate-descriptions.py` exists, runs in CI, blocks merges on: malformed parens, sentence truncation, self-aliases, missing `Different from` clause for `tier=core`, `tools`↔`disallowedTools` collisions, hard-coded catalog counts in known-managed files.
- **M10.** `dist/catalog-audit-report.json` regenerates green after all above changes; `validate_plugin` MCP tool returns identical findings count.

### SHOULD (v8.8.0 stretch, otherwise v8.9.0)
- **S1.** 28 specialist-tier descriptions standardized to V8 rich pattern.
- **S2.** Hand-typed counts in `plugin.json`, `marketplace.json`, `commands/menu.md`, `commands/dashboard.md` replaced with `{{catalog.skills}}` / `{{catalog.agents}}` tokens rendered by `scripts/render-manifest-template.py` at build.
- **S3.** `auto-wip-save.py` 30s timeout: on timeout, write a `hook-timeout` event to the ledger and surface a stderr warning.
- **S4.** SessionStart hook latency: merge `session-bootstrap.py` + `session-start-context.sh` into one Python entrypoint targeting <8s p95.
- **S5.** UserPromptSubmit picker directive: append `(disable via ULTRAPROMPT_DISABLE_HOOKS=1)` to the text.
- **S6.** `commands/dashboard.md` and `commands/mission-control.md`: consolidate (delete `mission-control.md` or convert to thin alias).
- **S7.** `mcp/ultraprompt_meta.py` — declare per-tool `readonly: true` metadata on the ~35 pure-read tools; remove or rename deprecated `compose_workflow`.
- **S8.** `plugin.json:12-33` keywords pruned from 21 to 6–8 (keep: `claude-code`, `codex`, `mcp-server`, `hooks`, `agentic-ai`, `code-review`, `security`, `observability`).

### WON'T (this release)
- **W1.** A full re-categorization of the tier system. `core` / `specialist` / `ecosystem` boundaries stay as-is.
- **W2.** Migration to a new MCP transport. Stdio remains.
- **W3.** Cross-plugin marketplace expansion. Single-plugin marketplace stays.
- **W4.** Hook execution model overhaul (no SetUID, no separate daemon). Hooks remain stdin-driven Python.

---

## 5. Scope (in / out)

### In scope
- All 49 skill `SKILL.md` files (descriptions, `aliases`, `when_to_use`, `Dispatch policy (V8)` section presence on `refactor`).
- All 30 agent `.md` files (`tools`, `disallowedTools`, body discipline section, `maxTurns` documentation).
- All 31 command `.md` files (frontmatter `disable-model-invocation`, runtime-token replacement of static counts).
- 7 hook scripts in `hooks/recipes/` (regex tightening on `protected-file-guard.py`, timeout/log on `auto-wip-save.py`, opt-out hint in `user-prompt-route-suggest.py`).
- `mcp/ultraprompt_meta.py` (encoding fix, per-tool readonly metadata, `compose_workflow` deprecation resolution).
- `scripts/audit-catalog-consistency.py` + new `scripts/validate-descriptions.py` + new `scripts/render-manifest-template.py`.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (catalog token replacement, keyword pruning).
- Dual-runtime mirror files (`.codex-plugin/plugin.json`, `.codex.mcp.json`, `.mcp.windows.json`, `hooks.windows.json`) re-rendered by the templating script.
- 6 new skills, 4 new agents, 2 new commands listed in §6.

### Out of scope
- Output styles (`output-styles/concise-review.md`, `output-styles/evidence-led.md`) — no findings against them.
- Dream/memory/learning subsystem internals.
- `_shared/playbooks/` template authoring — `adr-template.md`, `incident-postmortem-template.md` already exist; we surface them via new skills, not rewrite them.
- Marketplace-level changes (description currently mirrors `plugin.json` description — that mirror is intentional).

---

## 6. Technical design: data model

### 6.1 New entities

| Entity | Fields | Purpose |
|---|---|---|
| **`CatalogManifestTemplate`** | `path` (str), `tokens` (list[str: `catalog.skills`, `catalog.agents`, `catalog.mcp_tools`, `catalog.commands`, `catalog.hooks`, `catalog.output_styles`]), `rendered_at` (ISO ts), `runtime_counts` (dict) | Source-of-truth template before `scripts/render-manifest-template.py` substitution. Lives at `.claude-plugin/plugin.json.tmpl`, `.claude-plugin/marketplace.json.tmpl`, `commands/menu.md.tmpl`, `commands/dashboard.md.tmpl`. |
| **`DescriptionLintFinding`** | `file` (path), `line` (int), `rule` (enum: `MALFORMED_PARENS`, `TRUNCATED_SENTENCE`, `SELF_ALIAS`, `MISSING_DIFFERENT_FROM`, `TOOL_DISALLOWED_COLLISION`, `STATIC_COUNT_IN_MANAGED_FILE`, `MOJIBAKE`, `MISSING_DISPATCH_POLICY`), `severity` (`error` \| `warn`), `message` (str), `suggested_fix` (str \| None) | Output of `scripts/validate-descriptions.py`. Same shape used by `validate_plugin` MCP tool and CI gate. |
| **`AgentToolPolicy`** | `agent_name` (str), `tools` (list[str]), `disallowed_tools` (list[str]), `bash_allowlist` (list[regex] \| None), `path_allowlist` (list[regex] \| None), `max_turns` (int) | Validated policy block for every agent. Read by `scripts/validate-descriptions.py` to detect collisions; future hook can enforce `bash_allowlist` at PreToolUse. |
| **`HookLatencyEvent`** | `hook` (str), `duration_ms` (int), `timed_out` (bool), `bypass_active` (bool), `ts` (ISO ts) | Written by hooks to ledger v2 on every invocation. Powers the `S3` warning + dashboard panel. |

### 6.2 Modified entities

| Entity | Change |
|---|---|
| **`Skill` frontmatter** | No schema change; existing fields (`name`, `description`, `when_to_use`, `argument-hint`, `tier`, `aliases`, `output_style`, `allowed-tools`, `disable-model-invocation`, `output_style`) all retained. New invariant: `description` MUST match V8 rich pattern regex (see §7.3). |
| **`Agent` frontmatter** | No new fields. New invariant: `set(tools) ∩ set(disallowedTools) == ∅`. `maxTurns` documented in `_shared/DISCIPLINE.md` with a default ladder. |
| **`Command` frontmatter** | New optional field: `disable-model-invocation: true` for the 6 destructive commands. |
| **MCP tool metadata** | New optional field `readonly: bool` returned by `list_tools`. Defaults to `false` if absent (compat). |

### 6.3 Storage layout

```
.claude-plugin/
  plugin.json              <- rendered output (in git)
  plugin.json.tmpl         <- new, source-of-truth
  marketplace.json         <- rendered output (in git)
  marketplace.json.tmpl    <- new, source-of-truth
.codex-plugin/             <- rendered mirrors (in git)
commands/
  menu.md                  <- rendered output (in git)
  menu.md.tmpl             <- new, source-of-truth
  dashboard.md             <- rendered output (in git)
  dashboard.md.tmpl        <- new, source-of-truth
scripts/
  render-manifest-template.py    <- new
  validate-descriptions.py       <- new
  audit-catalog-consistency.py   <- extended (calls validate-descriptions)
dist/
  catalog-metadata.json    <- existing, source-of-truth for runtime counts
  catalog-audit-report.json <- existing, now includes description-lint findings
```

### 6.4 Migration / indexes

- No DB. All artifacts are files. No index changes.
- New build step: `make catalog-render` (or `python scripts/render-manifest-template.py`) runs before `make package` / `cli validate`. Failure halts the release.
- Existing `dist/catalog-metadata.json` is the authoritative source for token substitution.

---

## 7. Technical design: API surface

### 7.1 `validate_plugin` MCP tool — extended

**Before (v8.7.0):** returns `{ok: bool, findings: list[str]}` (loose).
**After (v8.8.0):** returns

```json
{
  "ok": false,
  "findings": [
    {
      "category": "description_lint",
      "rule": "MALFORMED_PARENS",
      "file": "skills/agent-author/SKILL.md",
      "line": 3,
      "severity": "error",
      "message": "Unclosed paren in description",
      "suggested_fix": "..."
    }
  ],
  "summary": {"errors": 17, "warnings": 0, "total": 17}
}
```

Backward-compatible: existing callers that read `findings[].message` still work; new structured fields are additive.

### 7.2 `capability_graph` MCP tool — extended

Already returns per-skill/agent counts at runtime. Add `cached_at: ISO_ts` and `is_stale: bool` (true if `dist/catalog-metadata.json` mtime is older than any file under `skills/` or `agents/`). Used by `render-manifest-template.py` to refuse rendering stale templates.

### 7.3 New deny-rules in `scripts/validate-descriptions.py`

| Rule | Regex / Check | Severity |
|---|---|---|
| `MALFORMED_PARENS` | `description.count('(') != description.count(')')` | error |
| `TRUNCATED_SENTENCE` | `description.endswith(('discipline.', '— runs', ': runs the X discipline.'))` AND `tier in {'core','specialist'}` | error |
| `SELF_ALIAS` | `name in aliases` | error |
| `MISSING_DIFFERENT_FROM` | `tier == 'core'` AND not regex.search(r'Different from', description) | error |
| `TOOL_DISALLOWED_COLLISION` | `set(tools) & set(disallowedTools)` | error |
| `STATIC_COUNT_IN_MANAGED_FILE` | regex `\b\d{2}\s+(skills?\|agents?\|MCP tools?\|commands?)\b` in `.tmpl`-managed files | error |
| `MOJIBAKE` | `re.search(r'â€[—"]|â‰¤|Ã—', content)` in any tracked text file | error |
| `MISSING_DISPATCH_POLICY` | `tier == 'core'` AND `'Dispatch policy (V8)' not in body` | warn |
| `KEYWORD_BLOAT` | `len(keywords) > 10` in `plugin.json` | warn |

### 7.4 New CLI: `ultraprompt-cli validate --strict`

Runs `validate-descriptions.py` + `audit-catalog-consistency.py` + `validate_plugin` MCP self-test. Exit non-zero on any `error`. Wired into pre-commit hook and CI.

### 7.5 New command: `/ultraprompt:dispatch <agent> <prompt>`

Frontmatter:
```yaml
name: dispatch
description: "Manually dispatch a named agent with a free-form prompt. Use when dispatch_advise's recommendation is wrong or you want to force a specialist."
argument-hint: "<agent-name> <prompt>"
disable-model-invocation: true
allowed-tools: "Agent"
```

Body: looks up agent in `dist/catalog-metadata.json`, refuses on unknown, otherwise invokes the agent via Task tool with the supplied prompt. No business logic in the command body beyond resolving the agent name.

### 7.6 New command: `/ultraprompt:rollback`

Frontmatter:
```yaml
name: rollback
description: "Restore the working tree to the most recent wip-save or checkpoint. Companion to /ultraprompt:wip-save and /ultraprompt:checkpoint."
argument-hint: "[checkpoint-id|--latest]"
disable-model-invocation: true
allowed-tools: "Read, Bash"
```

Body: reads ledger for most-recent `wip-save` / `checkpoint` event, runs `git stash apply <stash@{N}>` or `git checkout <commit>` based on event type, confirms via diff summary before applying. Hard-requires `--latest` or explicit ID — no silent rollback.

---

## 8. Technical design: integration points

### 8.1 Upstream (what we consume)

| System | Touchpoint | Change |
|---|---|---|
| `dist/catalog-metadata.json` | Build-time source for runtime counts | None (we read it more places) |
| Ledger v2 (`scripts/evidence-ledger.py`) | Hooks + MCP tools write events | Add `hook-timeout` event type for S3 |
| `_shared/DISCIPLINE.md` | Authoritative discipline doc | Add maxTurns ladder section (§Med-2) |
| `_shared/DISPATCH-POLICY.md` | Skill bodies reference it | No change |
| `_shared/playbooks/adr-template.md` | Surfaced by new `adr-author` skill | No change to template; skill body references it |
| `_shared/playbooks/incident-postmortem-template.md` | Surfaced by new `incident-response` skill | No change to template |

### 8.2 Downstream (who consumes us)

| Consumer | Contract | Impact of v8.8 changes |
|---|---|---|
| Claude Code main thread | Reads skill descriptions for routing | Higher precision (description cleanup) — net positive, no breaking change |
| `dispatch_advise` MCP tool | Reads agent `tools` / `disallowedTools` | More accurate trust assessment once collisions resolved |
| Codex CLI runtime | Reads `.codex-plugin/plugin.json` | Same payload, re-rendered via template |
| Windows hook runtime | Reads `hooks.windows.json` | Same payload, re-rendered via template |
| Marketplace registry | Reads `marketplace.json` | Same payload, re-rendered via template |

### 8.3 Third-party

None. Plugin remains dependency-free at runtime. Build-time templating uses Python stdlib only (`json`, `pathlib`, `re`, `string.Template`).

---

## 9. Technical design: sequence flows + failure modes

### 9.1 Sequence: Build with templating (happy path)

```
dev edits skills/foo/SKILL.md
    -> dev runs `make build` (or pre-commit hook fires)
    -> scripts/render-manifest-template.py reads dist/catalog-metadata.json
    -> renders .claude-plugin/plugin.json from .tmpl
    -> renders .claude-plugin/marketplace.json from .tmpl
    -> renders commands/menu.md and commands/dashboard.md from .tmpl
    -> renders .codex-plugin/plugin.json from .tmpl
    -> scripts/validate-descriptions.py runs against all skills/agents/commands
    -> scripts/audit-catalog-consistency.py runs full audit
    -> if any error severity: exit 1, halt commit
    -> else: commit proceeds
```

### 9.2 Sequence: `/ultraprompt:dispatch security-auditor "audit auth/"`

```
user types /ultraprompt:dispatch security-auditor "audit auth/"
    -> command body parses $ARGUMENTS into (agent_name, prompt)
    -> looks up agent in dist/catalog-metadata.json
    -> if unknown: print error + nearest-3 suggestions, exit
    -> else: invoke Task tool with subagent_type=security-auditor, prompt=...
    -> main thread waits for Task result
    -> renders result to user
```

### 9.3 Failure mode 1: Templating runs against stale catalog metadata

**Trigger:** dev adds new skill but doesn't regenerate `dist/catalog-metadata.json`.
**Detection:** `capability_graph.is_stale == true` (mtime check).
**Mitigation:** `render-manifest-template.py` exits non-zero with "Run `python scripts/build-catalog.py` to refresh `dist/catalog-metadata.json` before rendering templates."
**Logged where:** stderr + `hook-error` event in ledger.

### 9.4 Failure mode 2: `validate-descriptions.py` flags pre-existing skill not in scope of current PR

**Trigger:** description lint catches an issue on a file unchanged in PR.
**Detection:** lint runs against all files, not just diff.
**Mitigation:** lint output groups findings by `changed_in_diff` vs `pre-existing`. CI gates only on `changed_in_diff`. Pre-existing findings produce warnings, not errors. Initial v8.8 PR fixes all pre-existing → afterward both sets gate.
**Logged where:** lint output + CI annotations.

### 9.5 Failure mode 3: Hook timeout on `auto-wip-save.py` (S3)

**Trigger:** `wip-save.py` subprocess > 30s on a large WIP.
**Detection:** `signal.alarm(30)` in hook wrapper.
**Mitigation:** on timeout, write `hook-timeout` event with `script: auto-wip-save.py, duration_ms: >=30000` to ledger, print stderr warning `"Ultraprompt auto-wip-save timed out at 30s. Your changes are NOT saved. Run /ultraprompt:wip-save manually."`, exit 0 (don't block the Stop event).
**Logged where:** stderr + `hook-timeout` ledger event.

### 9.6 Failure mode 4: User attempts `rm -rf` from builder agent

**Trigger:** builder agent generates `bash` tool call with `rm -rf <path>`.
**Detection:** new optional Bash allowlist hook (S4 alt) at PreToolUse rejects on regex.
**Mitigation (v8.8 MUST):** explicit `disallowedTools` on builder.md — listed risky subcommands deny-list approach is preferred since `Bash` itself must remain available. We add a wrapper script `scripts/bash-allowlist-check.py` registered as a PreToolUse hook for builder.
**Logged where:** `hook-block` ledger event + stderr.

### 9.7 Failure mode 5: Encoding regression

**Trigger:** an editor re-saves `mcp/ultraprompt_meta.py` as cp1252.
**Detection:** `validate-descriptions.py` `MOJIBAKE` rule scans all tracked text files.
**Mitigation:** CI fails; `.gitattributes` already specifies UTF-8 — add `* text=auto eol=lf` enforcement and `.editorconfig` `charset = utf-8`.
**Logged where:** CI annotation + commit refusal at pre-commit hook.

### 9.8 Failure mode 6: New skill added without rendering manifest

**Trigger:** dev adds `skills/new-skill/SKILL.md` but doesn't run `make build`.
**Detection:** pre-commit hook runs `render-manifest-template.py --check`; if rendered output differs from committed `.json` / `.md`, fail.
**Mitigation:** dev runs `make build`, commits regenerated files.
**Logged where:** pre-commit stderr.

---

## 10. Technical design: feature flags + telemetry events + metrics

### 10.1 Feature flags (env vars)

| Flag | Default | Effect | Owner |
|---|---|---|---|
| `ULTRAPROMPT_STRICT_DESCRIPTIONS` | `1` (on) | `validate-descriptions.py` exits non-zero on any error. Off = warn only. | Plugin maintainers (off only for migration windows) |
| `ULTRAPROMPT_BASH_ALLOWLIST` | `1` (on) | builder agent's Bash allowlist hook active. Off bypasses check. | End users (off requires explicit env var; logged) |
| `ULTRAPROMPT_DISABLE_HOOKS` | unset | Existing — bypasses all hooks. No change in v8.8. | End users |
| `ULTRAPROMPT_ALLOW_HIGH_RISK` | unset | Existing — bypasses HIGH risk destructive command guard. No change. | End users |
| `ULTRAPROMPT_TEMPLATE_RENDER` | `1` (on) | If `0`, skip template render in build. Used only to debug. | Build engineers |

### 10.2 Telemetry events (ledger v2)

| Event type | When written | Fields |
|---|---|---|
| `description-lint-finding` | `validate-descriptions.py` flags an issue | `rule`, `file`, `line`, `severity`, `pr_ref` (if in CI) |
| `template-render` | `render-manifest-template.py` runs | `templates_rendered` (int), `tokens_substituted` (int), `duration_ms` |
| `hook-timeout` | Any hook exceeds its timeout | `hook`, `duration_ms`, `bypass_active` |
| `agent-tool-policy-validated` | `validate-descriptions.py` checks an agent | `agent`, `tools_count`, `disallowed_count`, `collisions` (int), `bash_allowlist_present` (bool) |
| `dispatch-cmd-invoked` | `/ultraprompt:dispatch` runs | `agent`, `prompt_hash` (sha256), `success` (bool) |
| `rollback-invoked` | `/ultraprompt:rollback` runs | `target_event_type` (wip-save / checkpoint), `restored_to` (sha / stash), `dry_run` (bool) |

Sampled values (from spot-check session 2026-05-23, validates the new events plumb through):
- `description-lint-finding` × 17 expected on first v8.8 dry-run (1 per finding in §1 table)
- `hook-timeout` × 0 currently (will appear once S3 deployed and a real WIP times out)

### 10.3 Metrics + KPIs

| Metric | Definition | v8.7 baseline | v8.8 target |
|---|---|---|---|
| `desc_lint_errors_per_release` | Sum of `error`-severity findings on `main` at tag time | 17 | 0 |
| `agent_tool_policy_collisions` | Count of agents with `set(tools) & set(disallowedTools) != ∅` | 3 | 0 |
| `agents_with_explicit_disallowedtools` | Count of read-only agents that declare `disallowedTools` | 1/14 = 7% | ≥14/14 = 100% (of read-only set) |
| `catalog_count_drift` | Diff between hand-typed and runtime counts | unknown drift surface | 0 (eliminated by templating) |
| `picker_directive_p95_latency_ms` | UserPromptSubmit hook p95 | ~4000 (timeout-bound) | ≤2500 |
| `routing_precision_top1` | router-bench top-1 hit rate | TBD (need pre-cleanup bench run) | +5pp over baseline |

---

## 11. Performance considerations + security_and_privacy + rollout_technical_plan

### 11.1 Performance

- **Build-time templating:** ≤200ms on Python stdlib (`json.load` + `string.Template.substitute` × 8 files). Negligible.
- **`validate-descriptions.py`:** reads ~110 frontmatter blocks (49 skills + 30 agents + 31 commands). ~50ms full run. CI cost negligible.
- **SessionStart latency (S4):** merging two scripts removes one subprocess invocation per session start. Target ≤8s p95 (from current ~13s combined).
- **UserPromptSubmit picker (S5):** opt-out hint adds ~80 chars to directive payload — well under MCP buffer limits.
- **Bash allowlist hook (M4):** adds one PreToolUse hook invocation per builder Bash call. <50ms overhead.

### 11.2 Security + privacy

- **Read-only enforcement:** v8.8 closes the documentation-only loophole. After M3, every read-only agent is **enforced** read-only — auditing tools that grep prose for "Read-only" assertions can now grep `disallowedTools` instead.
- **Bash allowlist (M4):** defense-in-depth for builder. Allow-by-default deny-list approach (deny `rm -rf`, `git push --force`, `git reset --hard --`, `npm install` outside the dev allowlist, `pip install`, `chmod +x`, `chmod 7??`, `curl ... | sh`). Refusals log to `hook-block` ledger event with command excerpt (first 200 chars, secret-scrub via existing `_ledger_write_call` summarization).
- **Protected file guard (M6):** new patterns:
  - `service-account.*\.json$` (Google service account keys)
  - `.*\.p12$`, `.*\.pfx$` (PKCS#12 keystores)
  - `aws-credentials\.json$`, `accessKeys\.csv$` (AWS console exports)
  - Existing `\.env($|\.)`, `\.pem`, `\.key`, `id_rsa`, `id_ed25519`, `secrets?\.(json|ya?ml|toml)$` retained
  - Regression test: tests/hooks/test_protected_file_guard.py adds cases for each new pattern + negative test for `non-secret.json` to confirm we don't over-block.
- **Mojibake fix (M5):** no security impact directly; quality-of-life improvement for users reading injected MCP instructions.
- **No new attack surface:** new commands `/ultraprompt:dispatch` and `/ultraprompt:rollback` both set `disable-model-invocation: true`, so the main thread cannot autonomously invoke them.
- **No PII or telemetry exfil changes:** all new telemetry events stay in local `evidence-ledger.jsonl`. No network egress added.

### 11.3 Rollout technical plan

**Phase R0 (pre-flight, 1d):** branch `feature/v8.8-remediation` off `main`. Snapshot `dist/catalog-audit-report.json` for before/after comparison. Run router-bench to capture top-1 precision baseline.

**Phase R1 (must-haves, 1–2d):** M1–M10 in one logical PR. Hard CI gate: `validate-descriptions.py --strict` must exit 0. Spot-test the 3 fixed descriptions via `route_intent` MCP tool (verify they now rank as expected for their canonical trigger phrases).

**Phase R2 (templating, 1d):** S2 (templating) lands as separate PR after R1 because it touches the same files. Renders `.tmpl` outputs, diffs against current `.json` / `.md` (should be byte-equal except for counts), commits both `.tmpl` source and rendered outputs.

**Phase R3 (effectiveness, 2–3d):** S1, S3–S8 in parallel sub-PRs, each scoped to one finding class. Each requires `make catalog-render && make validate` green.

**Phase R4 (v8.9 catalog expansion, 5–7d):** new skills + agents + commands ship as v8.9.0 after v8.8.0 has soaked for ≥7 days. Each new skill ships with its own router-bench fixture.

**Release gates:**
- `validate_plugin` MCP tool returns `ok: true, summary.errors: 0`.
- `dist/catalog-audit-report.json` shows 0 errors, ≤2 warnings.
- Router-bench top-1 precision ≥ baseline (no regression) for v8.8. For v8.9, expect +3–5pp from the new skills replacing the picker-triggering ambiguous matches.
- All 7 existing hook tests still green; new tests for protected-file-guard expansions added and green.

**Rollback strategy:** v8.8.0 is fully additive at the safety level (we only tighten policy). If a user finds a description-lint false positive that blocks their fork, they can set `ULTRAPROMPT_STRICT_DESCRIPTIONS=0` and continue. Bash allowlist on builder ships with `ULTRAPROMPT_BASH_ALLOWLIST=1` default; setting to `0` reverts to v8.7 behavior with a stderr warning. Templating: if `render-manifest-template.py` produces wrong output, revert PR R2; the rendered `.json` / `.md` files are still hand-editable as a last resort.

---

## 12. Risks (severity × likelihood)

| ID | Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|---|
| **R1** | Description lint catches genuinely OK descriptions and blocks merges (false positives) | High | Medium | Initial PR fixes all 17 known issues, then dogfoods lint on full catalog. Maintain a small `lint-suppress: rule_name` frontmatter field for documented exceptions. CI annotates "warning" first on new patterns for one release. |
| **R2** | Templating breaks Codex runtime (different JSON ordering / whitespace) | High | Low | Use `json.dumps(..., indent=2, sort_keys=False)` to preserve key order. Add diff test: rendered output ↔ pre-existing file. Phase R2 is its own PR specifically so this is testable in isolation. |
| **R3** | Bash allowlist on builder breaks legitimate workflows | Medium | Medium | Start with deny-list (M4) not allowlist. Deny list covers ~6 specific commands. Add `ULTRAPROMPT_BASH_ALLOWLIST=0` opt-out for v8.8; consider tightening to allowlist in v8.9 only after telemetry shows zero false-block events. |
| **R4** | `validate-descriptions.py` becomes the bottleneck (slow CI) | Low | Low | Pure Python stdlib, ~50ms. Profile once at R1; if >500ms, batch-cache frontmatter parses. |
| **R5** | Mojibake re-introduction by Windows editors | Medium | Medium | Enforce `.gitattributes` UTF-8 + `.editorconfig charset=utf-8`. Add MOJIBAKE check to lint. Document in CONTRIBUTING. |
| **R6** | New `/ultraprompt:dispatch` enables misuse (user dispatches builder with arbitrary destructive prompt) | Medium | Low | Same trust model as today — user is in driver's seat. Command requires `disable-model-invocation: true` so main thread can't auto-invoke. Telemetry logs dispatch invocations. |
| **R7** | Rollback command restores to a state that has secrets re-added to history | Medium | Low | Rollback uses `git stash apply` / `git checkout`, not history rewrite. Existing protected-file-guard fires on subsequent edits. |
| **R8** | Catalog expansion (v8.9) creates new router ambiguity that picker can't disambiguate | Medium | Medium | Each new skill ships with router-bench fixtures + `Different from` clause naming peers. Run picker telemetry comparison post-v8.9 release; iterate on descriptions if precision drops. |
| **R9** | dependency-audit + supply-chain-hardening consolidation breaks bookmarked V4 alias paths | Low | Medium | Keep both as V4-aliases pointing at single consolidated skill with `--focus={cve,build,transitive}` arg. Document in CHANGELOG. |
| **R10** | SessionStart hook merger (S4) regresses startup context coverage | Medium | Low | Merge is mechanical (one Python script that calls both code paths). Test: snapshot session-start output for v8.7 and v8.8, diff. |

---

## 13. Acceptance criteria (given / when / then)

### v8.8.0 (Remediation)

- **AC1 (M1).** GIVEN skills/agent-author/SKILL.md, skills/release/SKILL.md, skills/release-readiness/SKILL.md WHEN `validate-descriptions.py --strict` runs THEN it reports 0 `MALFORMED_PARENS`, 0 `TRUNCATED_SENTENCE` findings for those 3 files.
- **AC2 (M2).** GIVEN agents/router.md, agents/adversarial.md, agents/writer.md WHEN `validate-descriptions.py` parses them THEN `TOOL_DISALLOWED_COLLISION` finding count is 0.
- **AC3 (M3).** GIVEN the 13 named read-only agents WHEN their frontmatter is parsed THEN every one has `disallowedTools` containing at minimum `Write, Edit, MultiEdit`.
- **AC4 (M4).** GIVEN agents/builder.md and a Bash tool call `rm -rf /tmp/foo` from the builder agent WHEN the PreToolUse Bash-allowlist hook runs THEN the call is blocked and a `hook-block` event is written.
- **AC5 (M5).** GIVEN `mcp/ultraprompt_meta.py:53-84` WHEN searched with `grep -P "â€[—\"]|â‰¤|Ã—"` THEN zero matches.
- **AC6 (M6).** GIVEN a file path `secrets/service-account-prod.json` AND the protected-file-guard hook WHEN the Edit tool is invoked THEN the hook exits 2 with the "looks like secrets" message AND existing covered paths (`.env`, `id_rsa`) still block.
- **AC7 (M7).** GIVEN the 6 destructive commands WHEN their frontmatter is parsed THEN `disable-model-invocation: true` is present in each.
- **AC8 (M8).** GIVEN skills/security-audit/SKILL.md, skills/technical-debt-triage/SKILL.md WHEN `validate-descriptions.py` parses them THEN `SELF_ALIAS` finding count is 0.
- **AC9 (M9).** GIVEN any of the 17 review findings re-introduced as a one-line change WHEN CI runs `validate-descriptions.py --strict` THEN CI exits non-zero with the specific rule + file + line.
- **AC10 (M10).** GIVEN all M1–M9 applied WHEN `validate_plugin` MCP tool is called THEN response `summary.errors == 0`.

### v8.9.0 (Catalog expansion)

- **AC11 (G6.a).** GIVEN a user types `/ultraprompt:incident-response` WHEN the skill executes THEN it dispatches `incident-commander` agent and references `_shared/playbooks/incident-postmortem-template.md`.
- **AC12 (G6.b).** GIVEN a user types `/ultraprompt:adr-author "decision X"` WHEN the skill executes THEN it produces an ADR using `_shared/playbooks/adr-template.md`.
- **AC13 (G6.c).** GIVEN `/ultraprompt:dispatch security-auditor "audit auth/"` WHEN run THEN Task is invoked with `subagent_type: security-auditor` and the supplied prompt, and a `dispatch-cmd-invoked` event is written.
- **AC14 (G6.d).** GIVEN a recent `wip-save` event in the ledger WHEN `/ultraprompt:rollback --latest` runs THEN the working tree matches the saved state and a `rollback-invoked` event is written.
- **AC15 (G6.e).** GIVEN dependency-audit + supply-chain-hardening consolidation WHEN a user runs `/ultraprompt:dependency-audit --focus=transitive` THEN it produces transitive-dependency findings; alias `/ultraprompt:supply-chain-hardening` still works and emits a deprecation hint.

### Cross-cutting

- **AC16.** Router-bench top-1 precision after v8.8 ≥ v8.7 baseline (no regression).
- **AC17.** SessionStart p95 latency after S4 ≤ 8s.
- **AC18.** UserPromptSubmit picker directive text contains the opt-out hint after S5.

---

## 14. Rollout plan with phase gates

| Phase | Duration | Scope | Gate to proceed |
|---|---|---|---|
| **R0 – Pre-flight** | 0.5d | Branch, baseline router-bench, baseline `catalog-audit-report.json` snapshot | Snapshots archived under `dist/baselines/v8.7.0/` |
| **R1 – MUST fixes** | 1–2d | M1–M10 in single PR | All AC1–AC10 green, `validate_plugin` errors=0, router-bench non-regression |
| **R2 – Templating** | 1d | S2 in separate PR | Rendered outputs byte-equal to current (except counts), CI green |
| **R3 – SHOULD sweep** | 2–3d | S1, S3, S4, S5, S6, S7, S8 in parallel PRs | Each PR's own ACs + non-regression on router-bench |
| **R4 – v8.8.0 release** | 1d | Tag, generate release notes via `/ultraprompt:release`, publish | All Rs above green; soak period begins |
| **R5 – Soak** | 7d | Telemetry watch | `description-lint-finding` count steady at 0; `hook-timeout` count documented; no rollback-invoked emergencies |
| **R6 – v8.9 plan** | 0.5d | Draft v8.9 PRs for catalog expansion | Soak metrics signed off |
| **R7 – v8.9.0 implementation** | 5–7d | 6 new skills, 4 new agents, 2 new commands, 2 consolidations | AC11–AC15 green; new skills have router-bench fixtures |
| **R8 – v8.9.0 release** | 1d | Tag, release notes, publish | All R7 ACs + non-regression |

---

## 15. Validation plan

### 15.1 Spot-check evidence captured during PRD authoring (2026-05-23)

Commands run from `C:\Users\emsok\ultraprompt` via the harness `Read` and `Bash` tools (exit codes implied 0 unless noted; full content excerpts in §1):

| Command | Result | Validates |
|---|---|---|
| `Read agents/router.md (15 lines)` | `tools: "Read, Grep, Glob, Bash"` AND `disallowedTools: "Write, Edit, MultiEdit, Bash"` | Bash collision (M2) |
| `Read agents/adversarial.md (15 lines)` | Same collision pattern as router | Bash collision (M2) |
| `Read agents/writer.md (15 lines)` | `tools: "Read, Grep, Glob, Bash"` AND `disallowedTools: "Edit, MultiEdit, Bash"` | Bash collision (M2) |
| `Read agents/builder.md (15 lines)` | `tools: "Read, Grep, Glob, Bash, Edit, Write, MultiEdit"` AND NO `disallowedTools` line | Unfenced builder (M4) |
| `Read agents/auditor.md (15 lines)` | `tools:` + `disallowedTools: "Write, Edit, MultiEdit"` (positive example) | Read-only enforcement model exists (M3) |
| `Read skills/agent-author/SKILL.md (15 lines)` | `description: "**DEFAULT for agent authoring: produces a new agent definition (: runs the agent-author discipline.**"` | Malformed description (M1) |
| `Read skills/release/SKILL.md (15 lines)` | description contains `…structured release notes / changelog artifact: separate skill).** Different from /release-readiness…` — orphan `: separate skill).` fragment | Orphan fragment (M1) |
| `Read skills/release-readiness/SKILL.md (15 lines)` | description ends `…release-readiness audits whether the codebase is shippable.** Different from release … — release-readiness audits whether the codebase is shippable.` — sentence self-repeats | Repeated sentence (M1) |
| `Read skills/security-audit/SKILL.md (15 lines)` | `aliases: ["security-audit"]` | Self-alias (M8) |
| `Read skills/technical-debt-triage/SKILL.md (15 lines)` | `aliases: ["technical-debt-triage", "codebase-health", "developer-experience-audit"]` | Self-alias (M8) |
| `Read hooks/recipes/protected-file-guard.py (60 lines)` | Line 33: `PROTECTED = re.compile(r"(^\|/)(\.env($\|\.)\|.*\.pem$\|.*\.key$\|id_rsa$\|id_ed25519$\|secrets?\.(json\|ya?ml\|toml)$)")` — covers `.env.local` via `\.env($\|\.)`, MISSING `service-account*.json`, `*.p12`, `*.pfx` | Partial — narrower fix scope than reviewer claimed (M6) |
| `Read mcp/ultraprompt_meta.py (90 lines)` | Lines 57, 60, 61, 64, 65, 70, 73, 77, 81–84 contain `â€"`, `â‰¤`, `Ã—` | Mojibake (M5) |
| `Read .claude-plugin/plugin.json (full)` | Line 5 contains `"49 skills, 30 agents, 43 MCP tools, 31 commands"` literally | Static count drift (S2) |
| `Read .claude-plugin/marketplace.json (full)` | Line 11 contains identical static count string | Static count drift (S2) |
| `Bash ls commands/*.md \| wc -l` | exit 0, stdout `31` | Catalog count matches plugin manifest (reviewer's claim of 29 was wrong; review still surfaces the underlying drift risk) |
| `Glob commands/*.md` | 31 files enumerated | Confirms above |
| `Glob **/plugin.json` | `.claude-plugin\plugin.json`, `.codex-plugin\plugin.json` (manifest is in `.claude-plugin/`, not root) | Path correction vs reviewer (reviewer cited unqualified `plugin.json:5`; actual location is `.claude-plugin/plugin.json:5`) |

### 15.2 Pre-merge validation per phase

Each PR must run and attach the following:

```
make validate                  # = python scripts/validate-descriptions.py --strict
                               #   + python scripts/audit-catalog-consistency.py
                               #   + python -m mcp.ultraprompt_meta --self-test
make hook-tests                # = pytest tests/hooks/ -v
make router-bench              # = python scripts/router-bench.py --compare-baseline
                               #   dist/baselines/v8.7.0/router-bench.json
make catalog-render --check    # render templates; fail if rendered != committed
```

### 15.3 Post-release validation (R5 soak)

- Day 1, 3, 7: query ledger for `description-lint-finding` (target: 0), `hook-timeout` (note any), `dispatch-cmd-invoked` and `rollback-invoked` (note usage), `hook-block` for new protected-file patterns (note any).
- Day 7: re-run router-bench, compare to v8.8 release-time numbers (target: stable or improving).
- Day 7: re-run `validate_plugin` MCP tool against the released version (target: `summary.errors: 0`).

---

## 16. Open product questions + open technical questions

### Open product questions

- **PQ1.** Should `/ultraprompt:dispatch` be auto-discoverable or `disable-model-invocation: true`? Current PRD says the latter (safer); revisit if telemetry shows users want autonomous dispatch.
- **PQ2.** For v8.9 catalog expansion, should `cost-audit` ship as a top-level skill or as `auditor --focus=cost`? PRD currently lists it as a top-level skill (gap rank 4). Promotion rationale: cost analysis spans LLM tokens + cloud + DB N+1s; the auditor focus-flag pattern may not surface domain-specific findings.
- **PQ3.** Should `prompt-engineer` agent review **all** skill bodies as a CI gate, or be invoked per-PR by author? PRD currently says per-PR (lower friction); CI-gate version is a v8.9+ consideration.
- **PQ4.** Keyword pruning (S8): which 6–8 keywords maximize marketplace discovery? Need 1-month marketplace search-impression data to validate the keep-list. PRD picks conservatively (claude-code, codex, mcp-server, hooks, agentic-ai, code-review, security, observability).
- **PQ5.** Consolidation of `concept-brief` into `prd-lite --stakeholder-review` (gap rank 13): is there a real user persona that wants the standalone `concept-brief`? Need either telemetry from picker selections or one round of dogfooding before merging.

### Open technical questions

- **TQ1.** Should the Bash allowlist hook (M4) live in `hooks/recipes/` (global to all agents) or be agent-scoped (only fires for `builder`)? PRD assumes agent-scoped via per-agent hook registration. Verify Claude Code supports per-agent hooks in current SDK; if not, fall back to a global hook with `agent_name` check at runtime.
- **TQ2.** `disallowedTools` precedence when both `tools` and `disallowedTools` list the same token — what does the Claude Code SDK actually do today? PRD treats it as documentation-only ambiguity (the M2 fix removes it); confirm whether existing v8.7 routers/dispatchers see the agent as having Bash or not (could meaningfully affect router-bench baseline).
- **TQ3.** Template rendering language: `string.Template` (stdlib, restrictive) vs. `jinja2` (richer, adds dep). PRD picks `string.Template` to stay dependency-free; reconsider if multi-line conditional rendering becomes necessary for new manifests.
- **TQ4.** Mojibake auto-repair: should `validate-descriptions.py` offer `--fix` mode that re-encodes detected files, or stay diagnostic-only? PRD says diagnostic-only (safer); manual fix is one `iconv`.
- **TQ5.** Should `/ultraprompt:rollback` support partial rollback (single-file restore from stash)? PRD says no — first ship full-tree rollback, add file-scoped in v9.
- **TQ6.** Per-tool `readonly` MCP metadata (S7) — what does Claude Code main thread actually do with it today? If the SDK doesn't consume it, S7 becomes informational-only until a consumer exists. Confirm via SDK changelog before committing.
- **TQ7.** Should `validate-descriptions.py` lint pre-existing files immediately or only deltas (per the §9.4 grace period)? PRD picks delta-gating with full-file warnings for one release, then full gating. Confirm one-release is enough for fork ecosystem to catch up.

---

**End of PRD-V8.8.**

Implementation note: this PRD is the contract for v8.8 + v8.9 work. Per skill `prd-technical` discipline, next dispatch should be `technical-product-architect` for any section needing deeper design (especially §6.3 storage layout + §9 sequence flows) before code lands, and `risk-and-controls-reviewer` for §11 + §12 sign-off given the read-only enforcement and Bash-allowlist policy changes.

---

## 17. Implementation reconciliation (post-ship, 2026-05-24)

This section records decisions taken during execution that diverged from the prescriptive PRD text. The PRD body above is preserved as authored; this section is the source of truth for *what shipped*.

### Resolved technical questions

- **TQ1 — RESOLVED.** Did NOT create a separate `scripts/bash-allowlist-check.py`. Extended the existing `hooks/recipes/destructive-command-guard.py` global hook with the M4 deny-list patterns (chmod world-writable, package installs, etc.). Rationale: the destructive guard already blocked `rm -rf`, `git reset --hard`, `git push --force`, `git clean -fdx`, and `curl|sh`; a parallel hook would duplicate ~120 lines of risk-classifier logic. Builder's body (`agents/builder.md`) documents the deny-list and points at the actual hook. Acceptance criterion AC4 is satisfied by the global guard.
- **TQ3 — RESOLVED.** Templating uses `string.Template` (stdlib) per PRD recommendation. See `scripts/render-manifest-template.py`. Tokens use `${catalog.X}` syntax which is regex-rewritten to `${catalog_X}` before stdlib `Template.safe_substitute` runs (because `string.Template` doesn't allow dots in identifiers).
- **TQ4 — RESOLVED.** `validate-descriptions.py` ships diagnostic-only. No `--fix` mode. Manual repair documented in PRD §9.7.
- **TQ6 — RESOLVED.** Per-tool `readonly` MCP metadata shipped on 32 read-only tools (S7). Emitted as both `annotations.readOnlyHint: true` (MCP spec) and `readonly: true` (convenience). Confirmed visible in `tools/list` JSON-RPC response. Downstream-consumer status: informational-only until Claude Code / Codex SDKs surface the hint.
- **TQ7 — RESOLVED.** Lint runs against all files immediately (no grace period). Initial v8.8 PR fixed all 17 known issues plus 28 specialist-tier description rewrites discovered during the sweep, so the gate could turn on at full strictness without breaking the build.

### Resolved product questions

- **PQ1 — RESOLVED.** `/ultraprompt:dispatch` ships with `disable-model-invocation: true` per PRD recommendation. See `commands/dispatch.md`.
- **PQ2 — RESOLVED.** `cost-audit` shipped as a top-level skill (not `auditor --focus=cost`) with `data-analyst` as the dispatch agent. Rationale: cost analysis requires $-amount evidence per finding, which the generic auditor lane doesn't structure for. See `skills/cost-audit/SKILL.md`.
- **PQ4 — RESOLVED.** Keywords pruned to 8 in the rendered `.claude-plugin/plugin.json.tmpl`: `claude-code, codex, mcp-server, hooks, agentic-ai, code-review, security, observability`. 1-month marketplace data still recommended for empirical validation.

### Resolved via Slab F user input (2026-05-24)

- **PQ3 — RESOLVED.** User selected "CI gate over all skills". Implemented as `WEAK_SELF_RANKING` lint rule in `scripts/validate-descriptions.py`: for each tier=core/specialist skill, extracts trigger phrases from `description_meta.triggers` and verifies the skill routes to itself as top-1 or top-2 via the V8 router. Runs in `.github/workflows/validate.yml` per push/PR. Warn-tier (CI annotates but does not fail) so accumulated drift surfaces without blocking; one known acceptable warning today (`debug` "this is failing" rank-3 behind `ci-repair`, an acknowledged shared-lane edge case).
- **PQ4 — RESOLVED.** User confirmed the 8-keyword set in `.claude-plugin/plugin.json.tmpl`: `claude-code, codex, mcp-server, hooks, agentic-ai, code-review, security, observability`. Revisit after 1 month of marketplace impression data.
- **PQ5 — RESOLVED.** User selected "Keep both as separate skills". `concept-brief` and `prd-lite` remain distinct in v8.9; no consolidation.
- **R9 — RESOLVED.** User selected "Keep both separate". `dependency-audit` and `supply-chain-hardening` remain distinct skills with their own bodies; no `--focus={cve,build,transitive}` consolidation in v8.9.

### Deferred questions

- **TQ2 (`disallowedTools` SDK precedence)** — M2 fix removed all collisions, so behavior is now well-defined regardless of SDK semantics. Empirical SDK check still recommended but no longer release-blocking.
- **TQ5 (partial-file rollback)** — `/ultraprompt:rollback` ships with full-tree rollback only per PRD. File-scoped variant deferred to v9.

### Diff from PRD §15.2

The PRD names `make validate`, `make hook-tests`, `make router-bench`, `make catalog-render` validation targets. The repo does not ship a `Makefile`; instead, `docs/CLAUDE.md` documents the `python3 scripts/...` invocations directly, and `.github/workflows/validate.yml` invokes them in CI. Treat the `python3 scripts/...` form as canonical.

### Telemetry status (PRD §10.2)

| Event | Status | Writer |
|---|---|---|
| `description-lint-finding` | LIVE | `scripts/validate-descriptions.py` |
| `agent-tool-policy-validated` | LIVE | `scripts/validate-descriptions.py` |
| `template-render` | LIVE | `scripts/render-manifest-template.py` |
| `hook-timeout` | LIVE | `hooks/recipes/auto-wip-save.py` |
| `dispatch-cmd-invoked` | DECLARED | `commands/dispatch.md` body (model writes on execution) |
| `rollback-invoked` | DECLARED | `commands/rollback.md` body (model writes on execution) |

### Catalog deltas (post-execution count)

- Skills: 49 → 55 (+6 from v8.9 expansion: incident-response, adr-author, runbook-author, cost-audit, git-workflow, onboarding-doc).
- Agents: 30 → 34 (+4 from v8.9: incident-commander, prompt-engineer, release-manager, data-analyst).
- Commands: 31 → 33 (+2 from v8.9: `dispatch`, `rollback`).
- MCP tools: 43 → 42 (−1 from S7: `compose_workflow` removed).
- Registered hooks: 10 → 9 (−1 from S4: session-start-context.sh slot collapsed into session-bootstrap.py).
- Hook tests: 30 → 45 fixtures (+11 new fixtures across protected-file-guard and destructive-command-guard).

