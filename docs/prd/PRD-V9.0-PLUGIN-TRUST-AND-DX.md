# PRD-V9.0: Plugin Trust Completeness + Developer Experience

**Status:** Draft — pending review
**Owner:** Ultraprompt Toolkit
**Date:** 2026-05-25
**Target release:** Ultraprompt v9.0.0
**Source:** Plugin review of v8.9.0 (2026-05-25). 5 high-value improvements identified across MCP trust signals, hook coverage, code debt, safety-policy centralization, and contributor onboarding.

---

## 1. Problem statement + evidence

The v8.9.0 plugin review identified 5 concrete gaps that block "trust completeness" and "contributor velocity":

| Class | Evidence | Lane |
|---|---|---|
| Incomplete MCP risk metadata | `mcp/ultraprompt_meta.py --self-test` returns 42 tools; 32 carry `readOnlyHint: true` but 10 mutating tools (dashboard_launch, dashboard_stop, dream_run, gap_ledger_write, learning_apply, memory_forget, memory_promote, memory_write_candidate, mission_state, route_feedback) carry NO risk annotations. The MCP spec defines `destructiveHint`, `idempotentHint`, `openWorldHint` — clients cannot pre-warn users on first invocation. | Trust signal completeness |
| Safety-policy drift surface | `hooks/recipes/destructive-command-guard.py:41-93` contains CRITICAL/HIGH/MEDIUM denylist patterns. `agents/builder.md:93-107` carries a parallel prose denylist. Two surfaces, one intent — guaranteed to drift over time, which is exactly the failure class the V8.8 catalog templating eliminated. | Single source of truth |
| Sparse evidence ledger coverage | `claim_check` requires `validation_command: true` events in `~/.claude/plugins/data/ultraprompt-*/evidence-ledger.jsonl`. Today only `protected-file-guard.py`, `stop-validation-check.py`, and `scripts/validate-descriptions.py` write events. Bash/Edit/Write tool calls in the main thread leave NO trace unless they happen to hit those hooks. During V8.8 we had to manually seed validation events for `claim_check` to succeed — a workaround that contradicts the "evidence before claims" principle. | Auditability |
| Dead-code surface | `hooks/recipes/session-start-context.{sh,py}` unwired from `hooks/hooks.json` since V8.8 S4 merger but still referenced by `scripts/audit-doc-metadata.py:18` (looks for the .sh file as a doc-metadata source), `scripts/run-hook-tests.py:34` (registers the hook), and 2 fixtures under `tests/hooks/session-start-context/`. ~120 LOC stale. Confuses any contributor reading the hook registry. | Debt reduction |
| No external contributor entrypoint | 55 skills / 34 agents / 33 commands / 9 hooks; the generation pipeline (`source/*.json` → `scripts/regenerate-*` → `dist/`) is documented only in `docs/CLAUDE.md`, which is positioned as "repo notes". External contributors arriving via GitHub have no `CONTRIBUTING.md`, no "how to add a skill" recipe, no validation-gate checklist. Friction = silence. | Contributor velocity |

**Why this matters:** v8.8 closed the catalog-truth gap; v8.9 expanded the catalog. v9.0 makes the catalog *trustworthy* (R1, R3) and *extensible* (R2, R4, R5).

---

## 2. Users + jobs-to-be-done

| User | Jobs-to-be-done |
|---|---|
| **Claude Code / Codex end users** | Trust the safety annotations on MCP tools (R1). Get reliable `claim_check` verdicts that reflect actual session evidence, not seeded fixtures (R3). |
| **Plugin maintainers (Ultraprompt Toolkit)** | Change a denylist pattern in one place (R2). Audit hook coverage without grepping multiple files (R3). Onboard external contributors without 1:1 hand-holding (R5). |
| **External contributors** | Land their first skill or agent without reading 10 source files (R5). Trust the validate gate to catch their mistakes (R5 → existing). |
| **Compliance/security reviewers** | Read a single `_shared/safety-policy.yaml` to verify the deny-list (R2). Read a complete tool-risk table to certify the MCP surface (R1). Query ledger for any tool call to demonstrate audit coverage (R3). |

---

## 3. Goals + non-goals

### Goals

- **G1 — MCP trust completeness.** All 42 MCP tools declare full MCP-spec annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`). Downstream clients can drive UI based on the metadata.
- **G2 — Single safety-policy source.** One `_shared/safety-policy.yaml` is the source of truth for destructive-command patterns; the hook + the agent body both read from it.
- **G3 — Complete evidence ledger coverage.** Every PostToolUse fires a ledger event. `claim_check` becomes reliable without manual seeding.
- **G4 — Zero dead-code surface.** All unwired hooks removed; orphan references updated.
- **G5 — Contributor friendly.** `CONTRIBUTING.md` lets a new contributor land a skill in <10 minutes without reading internal docs.

### Non-goals

- **N1.** Rewriting the MCP server transport. Stdio remains.
- **N2.** Adding new MCP tools beyond the 42 from v8.9. Surface stays stable.
- **N3.** Changing the source-spec schema (`source/*.json`). Only adding documentation; not migrating data.
- **N4.** Changing existing safety policies. R2 is a refactor — same patterns, new location. New patterns are out of scope.
- **N5.** Real-time telemetry dashboards. The dashboard already exists; R3 adds source data but no new UI.

---

## 4. Must/should/won't-have requirements

### MUST (v9.0.0)

- **M1.** All 10 mutating MCP tools declare `destructiveHint`, `idempotentHint`, `openWorldHint` per MCP spec. The 32 read-only tools already declare `readOnlyHint: true` — these 10 fill in the rest.
- **M2.** `_shared/safety-policy.yaml` exists and is read by `hooks/recipes/destructive-command-guard.py` at startup. Patterns identical to v8.9.0 (refactor, not policy change).
- **M3.** `agents/builder.md` deny-list table is generated from the same `_shared/safety-policy.yaml` at agent-regeneration time (no hand-edited drift).
- **M4.** `hooks/recipes/post-tool-use-ledger.py` exists, registered in `hooks/hooks.json` + `hooks/hooks.windows.json` under `PostToolUse` matcher `*` (or empty matcher = all tools). Writes an event for every tool call with shape `{event: "PostToolUse", tool, validation_command, command_excerpt, file_path?, exit_code?, ts}`.
- **M5.** `hooks/recipes/session-start-context.{sh,py}` deleted. `scripts/audit-doc-metadata.py` updated to remove the reference. `scripts/run-hook-tests.py` deregistered. 2 fixtures under `tests/hooks/session-start-context/` deleted. Hook-test count drops from 45 → 43.
- **M6.** `CONTRIBUTING.md` at repo root. Sections: Quickstart, Source-of-truth files, Adding a skill (10 lines), Adding an agent (10 lines), Adding a hook (10 lines), Validation gate, How to test locally, How to ship a release.
- **M7.** `validate-descriptions.py` extended with new rule `MCP_RISK_HINTS_MISSING` that flags any MCP tool missing the 4 annotation keys (warns).
- **M8.** `dist/release-scorecard.json` reports `mcp_risk_annotations_coverage: 42/42`.
- **M9.** All v8.9 validators stay green: 0 description-lint errors, 0 catalog-consistency errors, 0 plugin-validator errors, ≥45 hook fixtures pass (the count will drop to 43 after R4 file removal — accept the new baseline), router-bench 56/56 (no regression).

### SHOULD (v9.0.0 stretch, otherwise v9.1.0)

- **S1.** Plugin manifest description trimmed to ≤200 chars + link to README. Saves SessionStart tokens.
- **S2.** Router-precision history in `dist/router-precision-history.json` (one entry per release tag): `{version, ts, top_1, top_3, weak_self_ranking_count}`. Lets the team track precision regression across versions.
- **S3.** `dist/release-scorecard.json` carries `schema_version: 1` so consumers can detect breaking shape changes.
- **S4.** A new `_shared/safety-policy.schema.json` JSON-Schema validator for the YAML, run in `validate-plugin.py`.
- **S5.** The `bash_guard` source metadata in `source/agent-specs.json` for the `builder` agent is removed (now redundant with `_shared/safety-policy.yaml`).

### WON'T (this release)

- **W1.** A V9 dispatch architecture rewrite.
- **W2.** Migration off Python stdlib for templating, hooks, or MCP.
- **W3.** Cross-plugin marketplace expansion.
- **W4.** A real-time tool-call streaming UI (dashboard already exists; R3 is source-data only).
- **W5.** Changing existing safety-policy patterns. v9 is a refactor.

---

## 5. Scope (in / out)

### In scope

- All 10 mutating MCP tool registrations in `mcp/ultraprompt_meta.py` (lines 1700–1900 region).
- `_shared/safety-policy.yaml` (new), and the two consumers: `hooks/recipes/destructive-command-guard.py` and `scripts/regenerate-agents.py` (for the builder body table).
- New `hooks/recipes/post-tool-use-ledger.py` + `hooks/hooks.json` + `hooks.windows.json` PostToolUse slot.
- Deletion of `hooks/recipes/session-start-context.sh`, `hooks/recipes/session-start-context.py`, `tests/hooks/session-start-context/*`, and references in `scripts/audit-doc-metadata.py`, `scripts/run-hook-tests.py`.
- New `CONTRIBUTING.md` at repo root.
- `scripts/validate-descriptions.py` (new `MCP_RISK_HINTS_MISSING` rule).
- `scripts/release-scorecard.py` (new `mcp_risk_annotations_coverage` field).
- V4-alias coverage retained where prior aliases existed.

### Out of scope

- Output-styles changes.
- Dream/memory/learning subsystem internals (R1 touches their MCP wrappers, not the underlying scripts).
- Marketplace structure changes.
- Source-spec schema changes.

---

## 6. Technical design: data model

### 6.1 New entities

| Entity | Fields | Purpose |
|---|---|---|
| **`SafetyPolicy`** | `version` (int), `critical_patterns` (list[{pattern: regex, description: str}]), `high_patterns` (same), `medium_patterns` (same), `last_updated` (ISO ts), `change_history` (list[str]) | Single source of truth for destructive-command denylist. Lives at `_shared/safety-policy.yaml`. Read at hook startup + agent-regen time. |
| **`PostToolUseEvent`** | `event: "PostToolUse"`, `tool: str`, `tool_input_summary: dict` (sanitized), `tool_response_summary: dict` (sanitized), `validation_command: bool` (per `is_validation_command()`), `protected_path: bool`, `risk_class: str ∣ None`, `session_id`, `ts: ISO` | Ledger entry shape emitted by the new PostToolUse hook. Subset of existing `summarize_payload()` in `evidence-ledger.py` so consumers don't change. |
| **`MCPToolAnnotations`** | `readOnlyHint: bool`, `destructiveHint: bool`, `idempotentHint: bool`, `openWorldHint: bool` | Per MCP spec. Already partially implemented for 32 read-only tools. R1 fills in the 10 mutating ones. |

### 6.2 Modified entities

| Entity | Change |
|---|---|
| **MCP `TOOLS` registry** | Tuple shape stays `(description, schema, handler, annotations?)`. Annotations dict expanded from `{"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}` to include all 4 keys for ALL 42 tools (currently only 32 carry annotations at all). |
| **`agents/builder.md`** | "Bash command safety (V8.8)" section table is now generated from `_shared/safety-policy.yaml` rather than hand-written. `regenerate-agents.py` does the substitution. |
| **`dist/release-scorecard.json`** | New top-level keys: `mcp_risk_annotations_coverage`, `safety_policy_version`, `schema_version` (S3 SHOULD). |

### 6.3 Storage layout

```
_shared/
  safety-policy.yaml         <- new, source of truth (R2)
  safety-policy.schema.json  <- new (S4, optional)
hooks/recipes/
  destructive-command-guard.py   <- modified: load from _shared/safety-policy.yaml
  post-tool-use-ledger.py        <- new (R3)
  session-start-context.sh       <- DELETED (R4)
  session-start-context.py       <- DELETED (R4)
tests/hooks/
  session-start-context/         <- DELETED dir (R4)
  post-tool-use-ledger/          <- new fixtures (R3)
scripts/
  audit-doc-metadata.py          <- modified: remove session-start-context.sh ref
  run-hook-tests.py              <- modified: remove session-start-context entry; add post-tool-use-ledger entry
  validate-descriptions.py       <- new MCP_RISK_HINTS_MISSING rule (M7)
  release-scorecard.py           <- new fields (M8 + S3)
CONTRIBUTING.md                  <- new (R5)
docs/prd/
  PRD-V9.0-PLUGIN-TRUST-AND-DX.md  <- this file
```

### 6.4 Migration / indexes

- No DB. All artifacts are files.
- `_shared/safety-policy.yaml` is the new file. To migrate without regression: write the YAML by reading patterns out of v8.9's `destructive-command-guard.py:41-93` verbatim; assert byte-equality of regex compilation outputs.
- Hook test count baseline shifts 45 → 43 (R4 removes 2 fixtures) → 43 + N (R3 adds new fixtures). Accept the rebaseline.

---

## 7. Technical design: API surface

### 7.1 `_shared/safety-policy.yaml` (new)

```yaml
version: 1
last_updated: "2026-05-25"
critical_patterns:
  - pattern: '\brm\s+-r?f?\s+/(?:\s|$)'
    description: "rm -rf at filesystem root"
  - pattern: '\bsudo\s+rm\s+-r?f?\s+/'
    description: "sudo rm at root"
  - pattern: ':\(\)\s*\{[^}]*:\s*\|\s*:'
    description: "fork bomb pattern"
  # ... all 9 CRITICAL entries from v8.9.0
high_patterns:
  - pattern: '\brm\s+-(?:rf|fr|r[a-z]*f|f[a-z]*r)\s+\S+'
    description: "rm -rf with target"
  # ... all 11 HIGH entries from v8.9.0 (incl. V8.8 chmod patterns)
medium_patterns:
  - pattern: '\brm\s+\S+'
    description: "rm (without -rf)"
  # ... all 16 MEDIUM entries from v8.9.0 (incl. V8.8 package-install patterns)
```

### 7.2 `hooks/recipes/destructive-command-guard.py` — modified

**Before (v8.9.0):** patterns inlined as Python literals at lines 41–93.
**After (v9.0.0):** load patterns from `_shared/safety-policy.yaml` at module-import time; compile to regex; classification logic unchanged. Fail-open if YAML missing (preserves "broken safety file should never block work" invariant — but writes a `safety-policy-load-error` ledger event for ops visibility).

### 7.3 `hooks/recipes/post-tool-use-ledger.py` — new

Signature (per Claude Code hook protocol):

```python
# stdin: JSON {event, tool_name, tool_input, tool_response, session_id, ts}
# stdout: empty (silent allow)
# stderr: empty unless ledger-write failed
# exit 0 always (fail-open)
```

Behavior:

1. Respect `ULTRAPROMPT_DISABLE_HOOKS=1` → exit 0.
2. Read stdin JSON. On parse error → exit 0.
3. Build summary via existing `evidence-ledger.py::summarize_payload` (already handles tool extraction + sensitive-key truncation).
4. Call `evidence-ledger.append_event("PostToolUse", summary)`.
5. exit 0.

### 7.4 `validate-descriptions.py` — new `MCP_RISK_HINTS_MISSING` rule

```python
def lint_mcp_risk_annotations(findings: list) -> None:
    """For each registered MCP tool, ensure annotations dict has all 4 keys
    per MCP spec (readOnlyHint, destructiveHint, idempotentHint, openWorldHint).
    """
    import mcp.ultraprompt_meta as m  # safe — module exposes TOOLS
    required = {"readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"}
    for name, entry in m.TOOLS.items():
        annotations = entry[3] if len(entry) > 3 else {}
        missing = required - set(annotations.keys())
        if missing:
            add(findings, "MCP_RISK_HINTS_MISSING", "warn",
                "mcp/ultraprompt_meta.py", 1,
                f"MCP tool '{name}' missing annotation keys: {sorted(missing)}",
                suggested_fix="Add destructiveHint/idempotentHint/openWorldHint per MCP spec.")
```

### 7.5 `CONTRIBUTING.md` — new

Section outline:

```markdown
# Contributing to Ultraprompt

## Quickstart
- Clone, ensure Python 3.11+, run `python3 scripts/validate-plugin.py` to confirm baseline green.
## Source of truth
- Skills: `source/skill-specs.json` → `python3 scripts/regenerate-skills.py`
- Agents: `source/agent-specs.json` → `python3 scripts/regenerate-agents.py`
- ...
## Adding a skill (10 lines)
[concrete recipe: append to JSON, regenerate, validate, commit]
## Adding an agent
## Adding a hook
## Adding an MCP tool
## Validation gate
- `python3 scripts/audit-catalog-consistency.py` (must exit 0)
- `python3 scripts/validate-descriptions.py` (must exit 0)
- `python3 scripts/run-hook-tests.py`
- `python3 scripts/run-router-bench.py`
- `python3 scripts/release-scorecard.py`
## Local testing
## Shipping a release
- Bump version in templates; render; tag; push.
```

---

## 8. Technical design: integration points

### 8.1 Upstream (what we consume)

| System | Touchpoint | Change |
|---|---|---|
| `dist/catalog-metadata.json` | Source of MCP-tool count (G1 reports 42/42) | None |
| `scripts/evidence-ledger.py` | `append_event`, `summarize_payload` | None — R3 hook uses existing API |
| `hooks/recipes/destructive-command-guard.py` | Existing pattern arrays | Replaced with YAML loader |
| `_shared/playbooks/*` | Builder-agent prose template | New: `safety-policy-table.md.tmpl` rendered into builder body |

### 8.2 Downstream (who consumes us)

| Consumer | Contract | Impact of v9.0 changes |
|---|---|---|
| Claude Code main thread | `tools/list` MCP response with annotations | Adds destructiveHint/idempotentHint/openWorldHint on 10 tools. Backward-compatible. |
| `claim_check` MCP tool | Reads ledger for `validation_command: true` events | Now sees ALL PostToolUse events, not just selected ones. More accurate verdict. |
| `dispatch_advise` MCP tool | Reads tool risk metadata | Same shape; more complete data. |
| `dashboard.py` SSE feed | Streams ledger events | Volume increases (PostToolUse now fires on every call). Performance check needed. |
| External contributors | `CONTRIBUTING.md` | New surface; existing repo structure unchanged. |

### 8.3 Third-party

None. v9 stays dependency-free at runtime.

---

## 9. Technical design: sequence flows + failure modes

### 9.1 Sequence: PostToolUse hook on a Bash tool call (happy path)

```
user invokes Bash {command: "python3 scripts/run-hook-tests.py"}
    -> Claude Code emits PreToolUse → destructive-command-guard.py (LOW → exit 0)
    -> tool runs
    -> Claude Code emits PostToolUse → post-tool-use-ledger.py
        -> reads stdin JSON
        -> summarize_payload sets validation_command=True (matches scripts/run-hook-tests.py)
        -> append_event("PostToolUse", {tool: "Bash", validation_command: True, ...})
        -> exit 0
    -> session continues, claim_check now sees this event
```

### 9.2 Sequence: safety-policy reload on hook re-invocation

```
destructive-command-guard.py imported by Claude Code hook runner
    -> on module import:
        -> open _shared/safety-policy.yaml
        -> if missing: log "safety-policy-load-error" event; fall back to empty patterns (every cmd is LOW)
        -> if present: parse, compile regexes once
    -> on stdin invocation:
        -> classify(cmd) against compiled patterns (unchanged from v8.9)
```

### 9.3 Sequence: agent-body regeneration with safety-policy table

```
contributor edits _shared/safety-policy.yaml
    -> runs python3 scripts/regenerate-agents.py
        -> loads safety-policy.yaml
        -> renders the "Bash command safety" section of agents/builder.md from a template
        -> diffs against on-disk; rewrites if changed
    -> commit + push
```

### 9.4 Failure mode 1: PostToolUse hook fails on every call (parse error in summarize)

**Trigger:** A tool returns an exotic `tool_response` shape that `summarize_payload` doesn't handle.
**Detection:** ledger does not receive a record; user notices `claim_check` says "no validation seen".
**Mitigation:** PostToolUse hook wraps the whole body in `try/except Exception: sys.exit(0)`. Worst case: that tool call isn't recorded; the session continues. We write a `hook-error` ledger event from a sibling try-block so ops can find these.
**Logged where:** stderr (suppressed in Claude Code production) + `hook-error` event.

### 9.5 Failure mode 2: ledger file disk-full

**Trigger:** `~/.claude/plugins/data/.../evidence-ledger.jsonl` write fails with ENOSPC.
**Detection:** `append_event` raises OSError.
**Mitigation:** `append_event` already wrapped in `try/except Exception: pass`. Hook exits 0. Lost telemetry is preferable to broken sessions.
**Logged where:** nowhere (intentional — silent in production; visible via `ULTRAPROMPT_DEBUG=1`).

### 9.6 Failure mode 3: YAML parse error in safety-policy

**Trigger:** Malformed YAML committed.
**Detection:** destructive-command-guard.py emits `safety-policy-load-error` event and falls back to "no patterns" (all commands LOW).
**Mitigation:** `validate-plugin.py` is extended (S4 SHOULD, M7 MUST for the schema check) to assert YAML parses and required keys exist. CI gate blocks merge.
**Logged where:** CI annotation + `safety-policy-load-error` ledger event at runtime.

### 9.7 Failure mode 4: PostToolUse hook latency spike

**Trigger:** Ledger write goes to a slow filesystem (e.g., network mount).
**Detection:** SessionStart latency budget breached if hook is slow.
**Mitigation:** Hook is async-safe by virtue of being a separate subprocess. Claude Code times out hooks at a configurable threshold (currently 3s for PreToolUse / unbounded for PostToolUse). We register PostToolUse with `timeout: 3`.
**Logged where:** Claude Code hook-timeout signal + `hook-timeout` event (PRD §10.2 from V8.8).

### 9.8 Failure mode 5: Dead-file removal breaks a downstream consumer

**Trigger:** R4 deletes `session-start-context.sh` but a third-party consumer (forks, blog posts) still references it.
**Detection:** No automatic detection; surfaces via user reports.
**Mitigation:** Document the removal in CHANGELOG. Keep the deletion atomic with the audit-doc-metadata.py update so internal references can't accidentally outlive the file.
**Logged where:** CHANGELOG.md + release notes.

### 9.9 Failure mode 6: Contributors regenerate skills but forget to commit `dist/`

**Trigger:** Newly authored skill in `source/skill-specs.json`; contributor commits source but not `dist/skill-index.json`.
**Detection:** `audit-catalog-consistency.py` exits non-zero on `dist/* is stale`.
**Mitigation:** `CONTRIBUTING.md` validation gate includes "git status before commit should show no `dist/` changes". CI gate already enforces this via the existing `--check` flags.
**Logged where:** PR CI annotation + local pre-commit (if enabled).

---

## 10. Technical design: feature flags + telemetry events + metrics

### 10.1 Feature flags (env vars)

| Flag | Default | Effect | Owner |
|---|---|---|---|
| `ULTRAPROMPT_DISABLE_HOOKS` | unset | Existing — disables ALL hooks including new PostToolUse. No change. | End users |
| `ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER` | unset | NEW (v9.0). Disables only the PostToolUse ledger hook (R3) while keeping other hooks. For users opting out of telemetry while keeping safety guards. | End users |
| `ULTRAPROMPT_SAFETY_POLICY_PATH` | unset | NEW (v9.0). Overrides `_shared/safety-policy.yaml` path for testing or organizational variants. | Plugin maintainers |
| `ULTRAPROMPT_DEBUG` | unset | Existing — surfaces internal errors to stderr. No change. | Plugin maintainers |

### 10.2 Telemetry events (ledger v2)

| Event type | When written | Fields |
|---|---|---|
| `PostToolUse` (existing event name; new writer) | Every tool call returns | `tool`, `tool_input_summary`, `tool_response_summary`, `validation_command`, `protected_path`, `risk_class`, `session_id`, `ts` |
| `safety-policy-load-error` | YAML missing or unparseable at hook import | `path`, `error_excerpt`, `fallback_active` |
| `safety-policy-loaded` | First successful load per session | `version`, `pattern_counts: {critical, high, medium}` |
| `mcp-risk-annotation-coverage` (release artifact, not runtime) | At release-scorecard generation | `coverage: 42/42`, `version` |

### 10.3 Metrics + KPIs

| Metric | Definition | v8.9 baseline | v9.0 target |
|---|---|---|---|
| `mcp_risk_annotations_coverage` | Count of MCP tools with all 4 annotation keys | 32/42 (only readOnlyHint subset) | 42/42 |
| `ledger_post_tool_use_coverage` | Fraction of tool calls in a session that produce a ledger event | unknown (manual sampling only) | ≥ 0.95 |
| `claim_check_unbacked_rate` | Fraction of claim_check calls returning UNBACKED | unknown (high in dev sessions) | < 0.20 |
| `safety_policy_load_errors_per_release` | Count of `safety-policy-load-error` events on `main` over a 7-day window | 0 (file didn't exist) | 0 |
| `contributor_PR_count_30d` | External PRs landing per 30 days post-CONTRIBUTING.md ship | 0 | qualitative only — measure narrative interest |

---

## 11. Performance considerations + security_and_privacy + rollout_technical_plan

### 11.1 Performance

- **PostToolUse hook (R3):** adds one subprocess invocation per tool call. Worst case in a heavy session: ~50 tool calls × 50ms hook overhead = 2.5s session-total. Acceptable. Optimization: hook reuses `evidence-ledger.append_event` which already buffers JSONL writes via `open(..., "a")` (no fsync per call). Profile after R3 ships; if p95 exceeds 80ms, consider batching.
- **Safety-policy YAML load (R2):** one read + parse on module import, ~5ms. Patterns compiled to regex once and cached. Zero per-call overhead vs v8.9.
- **Dashboard SSE stream:** event volume increases ~5-10× when PostToolUse fires on every call. Currently SSE pushes from `dashboard.py` polling the ledger. Confirm throughput before declaring R3 done.
- **MCP annotations (R1):** purely metadata; zero runtime cost.

### 11.2 Security + privacy

- **Ledger PII:** `summarize_payload` already redacts `stdout`, `stderr`, `output`, `content`, `text`, `diff`, `old_string`, `new_string` keys to length-bounded summaries. R3 inherits this. No new PII surface.
- **Safety-policy YAML:** patterns are public regex; no secrets. File is tracked in git.
- **PostToolUse hook bypass:** `ULTRAPROMPT_DISABLE_HOOKS=1` bypasses ALL hooks including safety guards. Already documented; no change.
- **Tenant isolation:** ledger lives per-runtime in `~/.claude/...` vs `~/.codex/...`. R3 inherits the existing directory choice via `_runtime_home_name()` in `ledger-v2.py`.

### 11.3 Rollout technical plan

**Phase R0 (pre-flight, 0.5d):** branch `feature/v9.0` off `main`. Snapshot `dist/release-scorecard.json` + router-bench for non-regression check.

**Phase R1 (MCP annotations, 0.5d):** M1 — add the 10 mutating-tool annotations. Update `build-capability-graph.py` if it consumes them. Verify `tools/list` JSON response. Run all validators.

**Phase R2 (safety-policy YAML, 1d):** M2 + M3 — extract YAML, refactor `destructive-command-guard.py` to load it, generate builder body table from YAML, regenerate agents. Byte-equal regex behavior verified via existing hook fixtures + 5 new fixtures specifically for the YAML load path.

**Phase R3 (PostToolUse hook, 1d):** M4 — new `post-tool-use-ledger.py`, register in hooks.json + hooks.windows.json, add ~6 fixtures covering Bash/Edit/Write/error/disabled-by-env. Confirm `claim_check` succeeds without manual seeding in a synthetic session.

**Phase R4 (dead-code cleanup, 0.5d):** M5 — delete files + remove references + delete fixtures. Hook-test baseline adjusts from 45 → 43 (then back up via R3 additions).

**Phase R5 (contributor docs, 0.5d):** M6 — author `CONTRIBUTING.md`. Link from README.

**Phase R6 (lint rule + scorecard, 0.5d):** M7 + M8 — new lint rule, new scorecard field.

**Phase R7 (release, 0.5d):** Tag v9.0.0; push; update marketplace.

**Phase R8 (soak, 7d):** Watch ledger for PostToolUse coverage; confirm dashboard performance; track first external contribution attempts.

**Release gates:**
- `validate_plugin` MCP tool returns `ok: true, summary.errors: 0`.
- `validate-descriptions.py` returns 0 errors / ≤2 warnings.
- `dist/release-scorecard.json` shows `mcp_risk_annotations_coverage: 42/42`, `safety_policy_version: 1`, CONCLUSION: READY.
- Router-bench top-1 ≥ baseline.
- Hook test fixtures: ≥43 pass after dead-code cleanup; ≥49 after R3 additions.

**Rollback strategy:** v9.0 is fully additive on the safety side (R1 + R2 + R3) — no policy change, only data-flow consolidation. R4 deletes files but contributors retain them in their forks if needed. If R3's PostToolUse hook degrades performance, set `ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER=1` to opt out without rebuild.

---

## 12. Risks (severity × likelihood)

| ID | Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|---|
| **R1** | PostToolUse hook latency degrades session throughput | Medium | Medium | Profile early in R3; default timeout of 3s; opt-out env var. If p95 > 80ms, batch writes. |
| **R2** | Safety-policy YAML refactor introduces a regex regression that misses a destructive command | High | Low | Byte-equal verification: load v9 YAML, compile regexes, diff compiled set against v8.9 Python literals. CI gate. Hook fixtures from v8.9 must continue to pass unchanged. |
| **R3** | Ledger event volume from R3 saturates `~/.claude/.../evidence-ledger.jsonl` over weeks | Low | Medium | Existing monthly rotation in `ledger-v2.py` already addresses this. Confirm rotation triggers under new volume. |
| **R4** | R4 deletion breaks a third-party reference (forks, blog posts) | Low | Low | CHANGELOG entry. Atomic delete. |
| **R5** | CONTRIBUTING.md misrepresents the source-spec schema if it drifts | Medium | Medium | Test the documented recipes during R5: literally follow the recipe to add a noop skill, validate, then revert. |
| **R6** | MCP `destructiveHint: true` on `memory_forget` blocks legitimate forget operations in clients that gate on it | Low | Low | The hint is advisory; clients should prompt, not block. If a downstream client over-gates, file an issue there. |
| **R7** | Safety-policy YAML parse error in production breaks safety enforcement (fail-open ≠ fail-safe) | High | Low | `validate-plugin.py` parses the YAML in CI. Pre-commit hook (recommended in CONTRIBUTING.md) catches this locally. Runtime fail-open is intentional: a broken safety file should never brick sessions. |
| **R8** | External contributors land low-quality skills that pass the validate gate but regress routing precision | Medium | Medium | `WEAK_SELF_RANKING` lint surfaces this. CI annotates. Reviewer (human + the new `prompt-engineer` agent from v8.9) is the final gate. |

---

## 13. Acceptance criteria (given / when / then)

### MUST

- **AC1 (M1).** GIVEN the MCP server is running v9.0.0 WHEN `tools/list` is called THEN every one of the 42 tools' `annotations` dict contains all 4 keys: `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`.
- **AC2 (M2).** GIVEN `_shared/safety-policy.yaml` exists WHEN `destructive-command-guard.py` imports THEN it loads patterns from the YAML AND classifies a sample `rm -rf /tmp/foo` as HIGH (identical to v8.9.0 behavior).
- **AC3 (M3).** GIVEN a contributor changes `_shared/safety-policy.yaml` WHEN `python3 scripts/regenerate-agents.py` runs THEN `agents/builder.md` "Bash command safety" table reflects the new patterns AND `regenerate-agents.py --check` succeeds.
- **AC4 (M4).** GIVEN `hooks/hooks.json` registers PostToolUse → `post-tool-use-ledger.py` WHEN a Bash tool call completes in a session THEN the evidence-ledger.jsonl gains a `{event: "PostToolUse", tool: "Bash", validation_command: <derived>}` record within 100ms.
- **AC5 (M5).** GIVEN v9.0.0 is checked out WHEN `find hooks/recipes/ -name 'session-start-context.*'` runs THEN result is empty AND `python3 scripts/run-hook-tests.py` reports ≥43 fixtures pass.
- **AC6 (M6).** GIVEN a new contributor follows `CONTRIBUTING.md` "Adding a skill" section verbatim WHEN they commit the new skill and run the validation gate THEN all listed validators exit 0.
- **AC7 (M7).** GIVEN a hypothetical MCP tool registered without all 4 annotation keys WHEN `python3 scripts/validate-descriptions.py` runs THEN it emits an `MCP_RISK_HINTS_MISSING` warning naming the tool.
- **AC8 (M8).** GIVEN v9.0.0 is at HEAD WHEN `python3 scripts/release-scorecard.py` runs THEN `dist/release-scorecard.json` contains `"mcp_risk_annotations_coverage": "42/42"`.
- **AC9 (M9).** GIVEN all M1-M8 applied WHEN the full validation suite runs THEN: validate-plugin 0/0, audit-catalog-consistency all OK, hook tests ≥43 pass, router-bench ≥56/56 top-1, release-scorecard CONCLUSION READY.

### SHOULD

- **AC10 (S1).** GIVEN plugin.json description WHEN measured THEN length ≤ 200 chars AND mentions "see README" or equivalent.
- **AC11 (S2).** GIVEN release-scorecard.py runs WHEN it completes THEN `dist/router-precision-history.json` has a new entry with `{version: 9.0.0, top_1: 56/56, weak_self_ranking_count: 1}`.
- **AC12 (S3).** GIVEN any v9.0.0 dist artifact WHEN inspected THEN it contains `schema_version` field.
- **AC13 (S4).** GIVEN a malformed `_shared/safety-policy.yaml` committed WHEN `validate-plugin.py` runs THEN it exits non-zero with a clear error pointing at the YAML line.

---

## 14. Rollout plan with phase gates

| Phase | Duration | Scope | Gate to proceed |
|---|---|---|---|
| **R0 – Pre-flight** | 0.5d | Baseline scorecard + router-bench snapshot | Snapshots archived under `dist/baselines/v8.9.0/` |
| **R1 – MCP annotations** | 0.5d | M1 (10 tools annotated) | AC1 green; tools/list inspection |
| **R2 – Safety-policy YAML** | 1d | M2 + M3 | AC2 + AC3 green; existing destructive-command-guard fixtures unchanged |
| **R3 – PostToolUse hook** | 1d | M4 + R3 fixtures | AC4 green; ledger coverage ≥0.95 in a synthetic 30-call session |
| **R4 – Dead-code cleanup** | 0.5d | M5 | AC5 green; hook-test count adjusts cleanly |
| **R5 – CONTRIBUTING.md** | 0.5d | M6 | Manual walkthrough succeeds |
| **R6 – Lint + scorecard** | 0.5d | M7 + M8 | AC7 + AC8 green |
| **R7 – Release** | 0.5d | Tag v9.0.0; push | AC9 green; release scorecard READY |
| **R8 – Soak** | 7d | Telemetry watch | PostToolUse coverage steady ≥0.95; no `safety-policy-load-error` events |

---

## 15. Validation plan

### 15.1 Pre-merge per phase

```
python3 scripts/validate-descriptions.py            # 0 errors expected
python3 scripts/audit-catalog-consistency.py        # all OK
python3 scripts/validate-plugin.py                  # 0 errors / 0 warnings
python3 scripts/run-hook-tests.py                   # ≥43 pass
python3 scripts/run-router-bench.py                 # 56/56 top-1
python3 scripts/render-manifest-template.py --check # in sync
python3 scripts/release-scorecard.py                # READY + coverage 42/42
python3 mcp/ultraprompt_meta.py --self-test         # exit 0; 42 tools annotated
```

### 15.2 R2-specific (safety-policy byte-equivalence)

```python
# scripts/verify-safety-policy-equivalence.py (new helper, optional)
import re, yaml
from hooks.recipes.destructive_command_guard import classify  # pre-refactor copy
v89_classify = classify  # snapshot
# After refactor:
from importlib import reload
import hooks.recipes.destructive_command_guard as guard
reload(guard)
# For each fixture in tests/hooks/destructive-command-guard/:
#   assert v89_classify(cmd) == guard.classify(cmd)
```

### 15.3 R3 ledger coverage check

```bash
# Synthetic session: run ~30 tool calls, then query ledger.
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ev','scripts/evidence-ledger.py')
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
events = [e for e in ev.read_events() if e.get('event') == 'PostToolUse']
print(f'PostToolUse events in last 24h: {len(events)}')
assert len(events) >= 1, 'PostToolUse coverage gap'
"
```

### 15.4 R5 contributor walkthrough

Manual: clone fresh; follow CONTRIBUTING.md "Adding a skill" recipe verbatim; commit; run validation gate; revert. Stopwatch ≤10 minutes.

### 15.5 Post-release soak (7d)

- Day 1, 3, 7: ledger query for `safety-policy-load-error` (target 0).
- Day 1, 3, 7: `PostToolUse` coverage (target ≥0.95 of tool calls in active sessions).
- Day 7: re-run router-bench; compare to v9.0 release-time numbers.
- Day 7: re-run `validate_plugin` against released package.

---

## 16. Open product questions + open technical questions

### Open product questions

- **PQ1.** Should `ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER` opt-out be default-off (current PRD) or default-on for telemetry-sensitive users? PRD picks default-off; revisit if privacy-focused adopters push back.
- **PQ2.** `destructiveHint: true` on `memory_forget` and `gap_ledger_write` — should these tools require explicit user confirmation in Claude Code's UI (if the SDK supports `requireConfirmation: true`)? Verify SDK capability before committing.
- **PQ3.** CONTRIBUTING.md tone: technical-precise (current PRD) or onboarding-warm? Pick after one external contributor reads it.

### Open technical questions

- **TQ1.** YAML library choice: `pyyaml` (battle-tested, ~2MB dependency) or stdlib parsing (no dependency but no YAML support; would force JSON). PRD picks `pyyaml`; revisit if dependency-free goal is reasserted.
- **TQ2.** PostToolUse hook timing: 3s timeout (PRD default) sufficient? Confirm against a slow filesystem (network mount) before declaring R3 done.
- **TQ3.** `mission_state` MCP tool has conditional mutation (write=true only). Should it carry `destructiveHint: true` always (conservative) or never (accurate to typical usage)? PRD picks `destructiveHint: true` (conservative; client can over-prompt safely).
- **TQ4.** Should `safety-policy.yaml` schema include `severity_overrides` for organizational variants (e.g., a regulated team that wants `pip install` as HIGH not MEDIUM)? PRD defers — single schema for v9.0; add overrides only if a real adopter asks.
- **TQ5.** R4 deletes session-start-context.{sh,py}. Should we also delete `_shared/playbooks/session-start-context-source.md` if it exists? Audit during R4 phase.

---

**End of PRD-V9.0.**

Implementation note: per skill `prd-technical` discipline, next dispatch is `risk-and-controls-reviewer` for sign-off on R3 (PostToolUse ledger introduces a new telemetry surface), then `builder` agent for R1 + R2 in parallel.
