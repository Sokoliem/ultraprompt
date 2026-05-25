# Plan: Ultraprompt v9.0 — Trust Completeness + Developer Experience

**Source PRD:** `docs/prd/PRD-V9.0-PLUGIN-TRUST-AND-DX.md`
**Date:** 2026-05-25
**Total estimate:** ~5d engineering + 7d soak.

This plan converts the v9.0 PRD into an executable, gate-driven sequence. Each phase is independently shippable (separate PR), gate-blocked by green validators, and reversible via env var.

---

## Phase R0 — Pre-flight (0.5d)

**Goal:** Establish v8.9.0 baselines so v9.0 regressions are detectable.

| Step | Action | Verify |
|---|---|---|
| 0.1 | `git checkout -b feature/v9.0 main` | `git branch --show-current == feature/v9.0` |
| 0.2 | `mkdir -p dist/baselines/v8.9.0/` | dir exists |
| 0.3 | `cp dist/release-scorecard.json dist/baselines/v8.9.0/release-scorecard.json` | file copied |
| 0.4 | `python3 scripts/run-router-bench.py > dist/baselines/v8.9.0/router-bench.txt` | top-1=56/56 captured |
| 0.5 | `python3 scripts/validate-descriptions.py --json > dist/baselines/v8.9.0/desc-lint.json` | 0 errors / 1 warning baseline |

**Gate:** all 5 files exist; baselines archived; branch ready.

---

## Phase R1 — MCP risk-annotation completeness (0.5d)

**Goal:** All 42 MCP tools declare all 4 MCP-spec annotation keys (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).

**Files modified:**
- `mcp/ultraprompt_meta.py` — annotate the 10 mutating tools.

**The 10 tools + annotations to add:**

| Tool | readOnlyHint | destructiveHint | idempotentHint | openWorldHint |
|---|---|---|---|---|
| `dashboard_launch` | false | false | true | false |
| `dashboard_stop` | false | true | true | false |
| `dream_run` | false | false | false | false |
| `gap_ledger_write` | false | false | false | false |
| `learning_apply` | false | true | false | false |
| `memory_forget` | false | true | true | false |
| `memory_promote` | false | false | true | false |
| `memory_write_candidate` | false | false | false | false |
| `mission_state` | false | true | true | false |
| `route_feedback` | false | false | true | false |

Reasoning:
- `dashboard_launch` is idempotent (re-launching opens the existing instance).
- `dashboard_stop` is destructive (kills the process) but idempotent (stopping a stopped process is a no-op).
- `dream_run` writes ledger events; not destructive of state, but each invocation creates new candidates (not idempotent).
- `gap_ledger_write` appends new entries; not destructive but not idempotent (duplicates accumulate without explicit dedupe).
- `learning_apply` mutates dispatch routing weights — destructive if applied to a misconfigured candidate.
- `memory_forget` destructive by definition; idempotent (forgetting already-forgotten = no-op).
- `memory_promote` idempotent (promoting already-promoted candidate); not destructive.
- `memory_write_candidate` not idempotent (new candidate per call).
- `mission_state` with `write=true` mutates `~/.ultraprompt/state/mission-state.json`; conservative `destructiveHint: true` (overwrites prior snapshot).
- `route_feedback` writes events; idempotent in effect (feedback signal accumulates) but each call is a new event.

**Workflow:**
1. Edit `mcp/ultraprompt_meta.py`: for each of the 10 tools, change the tuple from 3-element to 4-element with the annotations dict per the table above. Pattern:
   ```python
   "memory_forget": (
       "<description>",
       {<schema>},
       tool_memory_forget,
       {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
   ),
   ```
2. Verify `python3 mcp/ultraprompt_meta.py --self-test` shows 42/42 tools annotated.
3. Run validate-descriptions.py to confirm `MCP_RISK_HINTS_MISSING` rule (added in R6) returns 0.

**Gate:** AC1 green; `tools/list` JSON shows all 42 tools with all 4 annotation keys; no validator regressions.

---

## Phase R2 — Safety-policy YAML extraction (1d)

**Goal:** Centralize destructive-command patterns into `_shared/safety-policy.yaml`; `destructive-command-guard.py` and builder agent body both load from it.

**Files created/modified:**
- `_shared/safety-policy.yaml` (new) — extract CRITICAL/HIGH/MEDIUM pattern arrays from `hooks/recipes/destructive-command-guard.py:41-93`.
- `_shared/safety-policy.schema.json` (new, S4 stretch) — JSON-Schema for the YAML.
- `hooks/recipes/destructive-command-guard.py` — replace inline arrays with YAML loader; classification logic unchanged.
- `scripts/regenerate-agents.py` — at agent-regen time, inject the "Bash command safety" table into `agents/builder.md` body from the YAML.
- `source/agent-specs.json` — builder body template uses `{{safety_policy_table}}` placeholder.
- `agents/builder.md` (regenerated) — now generated table.
- `tests/hooks/destructive-command-guard/` — 5 new fixtures specifically for YAML-load path (missing YAML, malformed YAML, well-formed YAML with new pattern, etc.).

**Workflow:**
1. **Extract patterns to YAML.** Write `_shared/safety-policy.yaml` with `version: 1`, `last_updated: 2026-05-25`, three pattern arrays (`critical_patterns`, `high_patterns`, `medium_patterns`), each entry `{pattern, description}`. Patterns must be byte-equal to v8.9's Python literals.
2. **Refactor hook.** Edit `destructive-command-guard.py`:
   ```python
   import yaml  # or fall back to manual parse if pyyaml is rejected
   def _load_safety_policy():
       path = os.environ.get("ULTRAPROMPT_SAFETY_POLICY_PATH") or str(Path(__file__).resolve().parents[2] / "_shared" / "safety-policy.yaml")
       try:
           with open(path, encoding="utf-8") as f:
               data = yaml.safe_load(f)
           crit = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("critical_patterns", [])]
           high = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("high_patterns", [])]
           med = [(re.compile(p["pattern"], re.IGNORECASE), p["description"]) for p in data.get("medium_patterns", [])]
           _ledger_write("safety-policy-loaded", version=data.get("version"), critical_count=len(crit), high_count=len(high), medium_count=len(med))
           return crit, high, med
       except Exception as exc:
           _ledger_write("safety-policy-load-error", path=path, error=str(exc)[:200])
           return [], [], []  # fail-open
   CRITICAL_PATTERNS, HIGH_PATTERNS, MEDIUM_PATTERNS = _load_safety_policy()
   ```
3. **Byte-equivalence verification.** Write `.scratch/verify-safety-policy.py` (one-shot, not committed) that loads v8.9 patterns and v9 YAML patterns, compiles both, and asserts identical set of compiled-pattern strings.
4. **Generate builder body table.** Edit `scripts/regenerate-agents.py`:
   - At the top, add `def _load_safety_policy_table() -> str:` that loads YAML and renders a markdown table.
   - In `build_agent(spec)`, if `spec['name'] == 'builder'`, substitute `{{safety_policy_table}}` placeholder in the body with the rendered table.
   - In `source/agent-specs.json`, replace the current hand-written "Bash command safety" section in the builder body with a `{{safety_policy_table}}` placeholder.
5. **Regenerate** + verify `git diff agents/builder.md` shows only the table region changed, identical content.
6. **Hook fixtures.** Add `tests/hooks/destructive-command-guard/15-yaml-missing-allows.json`, `16-yaml-malformed-allows.json`, `17-yaml-loaded-blocks-rmrf.json`, `18-yaml-env-override.json`, `19-yaml-new-medium-pattern.json`.

**Gate:** AC2 + AC3 green; all v8.9 destructive-command-guard fixtures still pass; 5 new fixtures pass; hook test count adjusts cleanly; byte-equal verification clean.

---

## Phase R3 — PostToolUse evidence-ledger hook (1d)

**Goal:** Register a PostToolUse hook that captures every tool call to the evidence ledger, replacing the manual seeding pattern used in V8.8.

**Files created/modified:**
- `hooks/recipes/post-tool-use-ledger.py` (new, ~80 LOC).
- `hooks/hooks.json` — add PostToolUse slot with no matcher (matches all tools) + 3s timeout.
- `hooks/hooks.windows.json` — same.
- `tests/hooks/post-tool-use-ledger/` (new dir, ~6 fixtures).
- `scripts/run-hook-tests.py` — register `post-tool-use-ledger` hook entry.

**Hook implementation:**
```python
#!/usr/bin/env python3
"""V9.0 PostToolUse hook: append every tool call to the evidence ledger.

Fails open on any error. Respects:
- ULTRAPROMPT_DISABLE_HOOKS=1     (disables all hooks)
- ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER=1  (disables only this hook)
"""
from __future__ import annotations
import importlib.util, json, os, sys
from pathlib import Path

PR = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))

def main() -> int:
    if os.environ.get("ULTRAPROMPT_DISABLE_HOOKS") == "1": return 0
    if os.environ.get("ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER") == "1": return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if not isinstance(payload, dict): return 0
    try:
        spec = importlib.util.spec_from_file_location("ev", PR / "scripts" / "evidence-ledger.py")
        ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
        ev.append_event("PostToolUse", payload)
    except Exception:
        pass  # fail open; don't block tool result delivery
    return 0

if __name__ == "__main__":
    try: sys.exit(main())
    except Exception: sys.exit(0)
```

**hooks.json edit (add to existing PostToolUse-equivalent slot or create one):**
```json
"PostToolUse": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/recipes/post-tool-use-ledger.py",
        "timeout": 3
      }
    ]
  }
]
```

**Fixtures to add (`tests/hooks/post-tool-use-ledger/`):**
- `01-bash-validation-cmd.json` — Bash tool call running `pytest`; expect `validation_command: true` recorded.
- `02-bash-non-validation.json` — Bash tool call running `ls`; `validation_command: false`.
- `03-edit-protected-file.json` — Edit tool call on `.env`; `protected_path: true`.
- `04-write-regular-file.json` — Write tool call on `src/index.ts`.
- `05-malformed-payload-fails-open.json` — invalid JSON stdin; expect exit 0.
- `06-disable-env-bypass.json` — `ULTRAPROMPT_DISABLE_POST_TOOL_LEDGER=1`; expect no ledger write.

**Workflow:**
1. Author the hook script per spec above.
2. Add hook registration to `hooks/hooks.json` + `hooks/hooks.windows.json`.
3. Create fixtures.
4. Register in `scripts/run-hook-tests.py:HOOK_TO_SCRIPT`.
5. Run hook tests → expect ≥49 fixtures pass (43 from R4 baseline + 6 new).
6. Synthetic ledger-coverage check (see PRD §15.3).

**Gate:** AC4 green; PostToolUse coverage ≥0.95 of tool calls in synthetic session; all fixtures pass.

---

## Phase R4 — Dead-code cleanup (0.5d)

**Goal:** Remove unwired `session-start-context.{sh,py}` and all references.

**Files deleted:**
- `hooks/recipes/session-start-context.sh`
- `hooks/recipes/session-start-context.py`
- `tests/hooks/session-start-context/01-empty-input.json`
- `tests/hooks/session-start-context/02-disable-env.json`
- `tests/hooks/session-start-context/` (empty dir)

**Files modified:**
- `scripts/audit-doc-metadata.py:18` — remove `ROOT / "hooks" / "recipes" / "session-start-context.sh",` from the list.
- `scripts/run-hook-tests.py:34` — remove `"session-start-context": HOOKS_DIR / "session-start-context.py",` entry from `HOOK_TO_SCRIPT`.

**Workflow:**
1. `git rm hooks/recipes/session-start-context.{sh,py}`
2. `git rm -r tests/hooks/session-start-context/`
3. Edit the two scripts to remove references.
4. Run hook tests → expect 43 fixtures pass (45 v8.9 baseline − 2 removed).
5. Confirm `python3 scripts/audit-doc-metadata.py` still passes.

**Gate:** AC5 green; hook test count = 43 (will rebase up to 49+ after R3 fixtures merge if done out of order — both phases land before R7).

---

## Phase R5 — CONTRIBUTING.md (0.5d)

**Goal:** Single onboarding document for external contributors.

**File created:** `CONTRIBUTING.md` at repo root.

**Section outline (~150 lines):**
```markdown
# Contributing to Ultraprompt

Thank you for your interest. Ultraprompt is a Claude Code + Codex plugin with 55+ skills, 34+ agents, and a hook + MCP surface. This guide is your shortest path from clone to merged PR.

## Quickstart

git clone <repo>
cd ultraprompt
python3 scripts/validate-plugin.py  # should exit 0

## Source of truth

| What you edit | What runs | What gets regenerated |
|---|---|---|
| `source/skill-specs.json` | `python3 scripts/regenerate-skills.py` | `skills/*/SKILL.md`, `dist/skill-index.json` |
| `source/agent-specs.json` | `python3 scripts/regenerate-agents.py` | `agents/*.md`, `dist/capability-graph.json` |
| `source/panel-specs.json` | (no regenerator yet) | `dist/capability-graph.json` |
| `mcp/ultraprompt_meta.py` | (direct edit) | `dist/capability-graph.json` |
| `_shared/safety-policy.yaml` | `python3 scripts/regenerate-agents.py` | `agents/builder.md` (table region) |

**Never edit `skills/*/SKILL.md` or `agents/*.md` directly** — they are generated. Edit the source JSON instead.

## Adding a skill (10 lines)

1. Append an entry to `source/skill-specs.json` matching the existing schema (name, title, tier, description, when_to_use, ...).
2. `python3 scripts/regenerate-skills.py`
3. `python3 scripts/build-skill-index.py`
4. `python3 scripts/build-catalog-metadata.py`
5. `python3 scripts/build-capability-graph.py`
6. `python3 scripts/validate-descriptions.py` (must exit 0; warnings ok)
7. `python3 scripts/audit-catalog-consistency.py` (must exit 0)
8. `python3 scripts/run-router-bench.py` (top-1 ≥ baseline)
9. Add at least one router-bench positive case for your skill's primary trigger in `tests/routing/` if applicable.
10. Commit `source/skill-specs.json`, the regenerated files, and dist/* — all together.

## Adding an agent

Same shape as Adding a skill but for `source/agent-specs.json` → `scripts/regenerate-agents.py`. Pay attention to `tools` and `disallowed_tools` — read-only agents must declare `disallowed_tools: "Write, Edit, MultiEdit"` per V8.8 invariants.

## Adding a hook

1. Author `hooks/recipes/<your-hook>.py`. Must respect `ULTRAPROMPT_DISABLE_HOOKS=1` and fail-open on any error (`try/except Exception: sys.exit(0)`).
2. Register in `hooks/hooks.json` and `hooks/hooks.windows.json` under the appropriate event slot (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`, `SessionEnd`, `UserPromptSubmit`, `SubagentStart`).
3. Add fixtures under `tests/hooks/<your-hook>/`.
4. Register in `scripts/run-hook-tests.py:HOOK_TO_SCRIPT`.
5. Run `python3 scripts/run-hook-tests.py` — all fixtures pass.

## Adding an MCP tool

1. Edit `mcp/ultraprompt_meta.py`: add a new entry to the `TOOLS` dict with shape `(description, schema, handler, annotations)` where annotations is a dict with all 4 keys (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`).
2. Implement the handler function above the TOOLS dict.
3. Run `python3 mcp/ultraprompt_meta.py --self-test` (must exit 0).
4. Run `python3 scripts/build-capability-graph.py`.
5. Run `python3 scripts/validate-descriptions.py` — confirm no `MCP_RISK_HINTS_MISSING` warning for your tool.

## Validation gate (before opening a PR)

python3 scripts/validate-descriptions.py
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
python3 scripts/run-hook-tests.py
python3 scripts/run-router-bench.py
python3 scripts/render-manifest-template.py --check
python3 scripts/release-scorecard.py

All must exit 0. The CI workflow at `.github/workflows/validate.yml` runs the same suite on every push and PR.

## Local testing

(Document how to install your branch into Claude Code or Codex for live testing.)

## Shipping a release (maintainers only)

1. Bump version in `.claude-plugin/plugin.json.tmpl` + `.claude-plugin/marketplace.json.tmpl` + `.codex-plugin/plugin.json` + `README.md`.
2. Render: `python3 scripts/render-manifest-template.py`
3. Rebuild dist: catalog-metadata + capability-graph + skill-index.
4. Run validation gate.
5. Commit + tag (e.g., `git tag v9.0.0`) + `git push --tags`.

## Code of conduct

(link to existing or inherit from Anthropic plugin standards)

## Reaching maintainers

Open an issue at github.com/Sokoliem/ultraprompt for design questions before sending a large PR.
```

**Workflow:**
1. Author `CONTRIBUTING.md` per outline above.
2. Add link from `README.md` ("## Contributing — see CONTRIBUTING.md").
3. Walkthrough test: literally follow the "Adding a skill" recipe with a noop skill named `_test-noop`, validate, revert.

**Gate:** AC6 green; walkthrough stopwatch ≤10 minutes.

---

## Phase R6 — Lint rule + scorecard fields (0.5d)

**Goal:** v9 stays in lint compliance automatically; release scorecard surfaces MCP coverage.

**Files modified:**
- `scripts/validate-descriptions.py` — add `lint_mcp_risk_annotations(findings)` per PRD §7.4.
- `scripts/release-scorecard.py` — add `mcp_risk_annotations_coverage`, `safety_policy_version`, `schema_version: 1` fields.

**Workflow:**
1. Add the lint function (re-uses `mcp/ultraprompt_meta.py` TOOLS import).
2. Wire into `run_lint()`.
3. Add new fields to release-scorecard.
4. Run validators to confirm 0 errors / no new warnings (since R1 already annotated all 42 tools).

**Gate:** AC7 + AC8 green; release-scorecard schema_version=1 visible.

---

## Phase R7 — Release (0.5d)

**Goal:** Tag v9.0.0; push to marketplace.

**Workflow:**
1. Bump version: edit `.claude-plugin/plugin.json.tmpl`, `marketplace.json.tmpl`, `.codex-plugin/plugin.json`, `README.md`, `docs/CLAUDE.md`, `hooks/recipes/session-bootstrap.py` banner from 8.9.0 → 9.0.0.
2. `python3 scripts/render-manifest-template.py`
3. Rebuild dist artifacts.
4. Run full validation suite.
5. `git commit -am "Bump ultraprompt to v9.0.0"`
6. `git tag v9.0.0 -m "Ultraprompt v9.0.0 — trust completeness + DX"`
7. `git push origin main && git push origin v9.0.0`
8. `/plugin` in Claude Code to refresh marketplace.

**Gate:** AC9 green; release-scorecard CONCLUSION READY; tag visible on GitHub.

---

## Phase R8 — Soak (7d)

**Goal:** Observe v9.0 in real sessions; confirm no regressions.

**Daily checks (Day 1, Day 3, Day 7):**

```bash
# safety-policy load errors (target: 0)
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('led','scripts/ledger-v2.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
errors = mod.read_events(days=1, event_types=['safety-policy-load-error'])
print(f'safety-policy-load-error count: {len(errors)}')
"

# PostToolUse coverage in a representative session
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('ev','scripts/evidence-ledger.py')
ev = importlib.util.module_from_spec(spec); spec.loader.exec_module(ev)
events = ev.read_events()
post = [e for e in events if e.get('event') == 'PostToolUse']
print(f'PostToolUse events in ledger: {len(post)}')
"

# Router-bench non-regression
python3 scripts/run-router-bench.py | grep top-1
```

**Day 7 actions:**
- Re-run `python3 scripts/release-scorecard.py` → READY.
- Re-run `python3 scripts/validate-plugin.py` → 0 errors.
- Compare PostToolUse event volume to projection. If >2× projected, file a follow-up to add batching (NOT release-blocking).

**Soak gate:** zero `safety-policy-load-error` events; PostToolUse coverage trending up; no router-bench regressions.

---

## Risks at the plan level

| ID | Risk | Mitigation |
|---|---|---|
| **PR1** | R3 PostToolUse hook degrades session latency below SLA | Profile on Day 1 of soak; opt-out env var ready. If sustained >80ms p95, file follow-up to batch writes. |
| **PR2** | R2 YAML refactor regression on a destructive command | Byte-equal verification helper in `.scratch/`; v8.9 fixtures must pass unchanged. |
| **PR3** | R4 deletion breaks fork users | CHANGELOG entry; atomic with audit-doc-metadata.py update. |
| **PR4** | R5 CONTRIBUTING.md misrepresents the schema | Walkthrough test before merge; revisit after first external PR. |
| **PR5** | OAuth `workflow` scope still missing → CI workflow file can't be pushed | Pre-flight: confirm token has `workflow` scope before R6 or commit workflow update via GitHub web UI. |

---

## Parallel-execution map

The phases below can run concurrently (no shared file edits):

```
R0  pre-flight
 │
 ├──> R1 (mcp annotations)        ──┐
 │                                  │
 ├──> R2 (safety-policy YAML)     ──┤
 │                                  │
 ├──> R3 (PostToolUse hook)       ──┤
 │                                  │
 ├──> R4 (dead-code cleanup)      ──┤── all must complete → R6 → R7 → R8
 │                                  │
 ├──> R5 (CONTRIBUTING.md)        ──┘
 │
 └──> (sequence converges at R6)
```

R6 (lint rule + scorecard fields) depends on R1 (so the lint can verify all 42 tools annotated) and R5 (so CONTRIBUTING.md can reference the new rule). R7 release depends on all prior.

---

## Definition of done

- All M1-M9 acceptance criteria green.
- v9.0.0 tag pushed.
- Marketplace refresh shows v9.0.0.
- 7-day soak completes with zero `safety-policy-load-error` events.
- One external contributor's first PR lands successfully OR CONTRIBUTING.md walkthrough completes in ≤10 minutes by an unfamiliar reader.

---

## Open questions (forwarded from PRD §16)

PQ1, PQ2, PQ3, TQ1, TQ2, TQ3, TQ4, TQ5 — see PRD for resolution paths. PRD-defaults stand for execution; user input only needed if a default fails.
