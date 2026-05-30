# Contributing to Ultraprompt

Thank you for your interest. Ultraprompt is a Claude Code + Codex plugin with a broad, templated catalog of skills, agents, commands, MCP tools, and hooks. This guide is your shortest path from clone to merged PR. (Exact catalog counts live in `dist/catalog-metadata.json`, computed from disk — this doc deliberately avoids hard-coded numbers that would drift.)

## Quickstart

```bash
git clone https://github.com/Sokoliem/ultraprompt.git
cd ultraprompt
python3 scripts/validate-plugin.py    # baseline must exit 0 before you change anything
```

Confirm green output. If it isn't, file an issue first — your environment may be missing Python 3.11+ or a stdlib component the validators rely on.

## Source of truth

Generated files live alongside their sources. **Never edit `skills/*/SKILL.md`, `agents/*.md`, or `dist/*.json` directly** — they are regenerated from the table below.

| What you edit | What runs | What gets regenerated |
|---|---|---|
| `source/skill-specs.json` | `python3 scripts/regenerate-skills.py` | `skills/*/SKILL.md`, `dist/skill-index.json` |
| `source/agent-specs.json` | `python3 scripts/regenerate-agents.py` | `agents/*.md`, `dist/capability-graph.json` |
| `source/panel-specs.json` | `python3 scripts/build-capability-graph.py` (no skill/agent regenerator) | `dist/capability-graph.json` |
| `source/dream-jobs.json` | `python3 scripts/build-capability-graph.py` | `dist/capability-graph.json` |
| `_shared/safety-policy.json` | `python3 scripts/regenerate-agents.py` | `agents/builder.md` (Bash safety table region) + reloaded at hook startup |
| `.claude-plugin/plugin.json.tmpl` | `python3 scripts/render-manifest-template.py` | `.claude-plugin/plugin.json` |
| `.claude-plugin/marketplace.json.tmpl` | same | `.claude-plugin/marketplace.json` |
| `commands/menu.md.tmpl` | same | `commands/menu.md` |
| `commands/dashboard.md.tmpl` | same | `commands/dashboard.md` |
| `mcp/ultraprompt_meta.py` | (direct edit) | `dist/capability-graph.json` |

After any change, rebuild dist artifacts:

```bash
python3 scripts/build-catalog-metadata.py
python3 scripts/build-skill-index.py
python3 scripts/build-capability-graph.py
```

## Adding a skill

```bash
# 1. Append an entry to source/skill-specs.json. Use an existing skill as a template
#    (e.g. skills/dependency-audit is a clean specialist-tier example).
# 2. Regenerate + rebuild:
python3 scripts/regenerate-skills.py
python3 scripts/build-skill-index.py
python3 scripts/build-catalog-metadata.py
python3 scripts/build-capability-graph.py
# 3. Validate:
python3 scripts/validate-descriptions.py           # must exit 0; warnings ok
python3 scripts/audit-catalog-consistency.py       # must exit 0
python3 scripts/run-router-bench.py                # top-1 must stay ≥ baseline
# 4. (Optional) Add a router-bench positive case in tests/routing/ for your skill's primary trigger.
# 5. Commit source/skill-specs.json, the regenerated files, and dist/* — all in one commit.
```

### Description shape (V8 rich pattern, enforced by lint)

Every skill description must follow the V8 rich pattern or `validate-descriptions.py` will reject it:

```
**DEFAULT for <X> — <what it produces>.** Different from /<peer-skill> (<why>), /<peer-skill> (<why>). Triggers: '<phrase>, <phrase>, <phrase>'.
```

Lint rules in scope:

| Rule | Severity | Triggered when |
|---|---|---|
| `MALFORMED_PARENS` | error | description has unbalanced parens |
| `TRUNCATED_SENTENCE` | error | description ends with `: runs the X discipline.**` (sparse fallback) |
| `SELF_ALIAS` | error | aliases list contains the skill's own name |
| `MISSING_DIFFERENT_FROM` | error | `tier=core` skill lacks `Different from` clause |
| `WEAK_SELF_RANKING` | warn | skill doesn't route to itself for its declared triggers |

## Adding an agent

Same shape as Adding a skill but for `source/agent-specs.json` → `python3 scripts/regenerate-agents.py`.

Pay attention to:

- `tools` and `disallowed_tools` must NOT share any token (`TOOL_DISALLOWED_COLLISION` lint blocks merge).
- Read-only agents MUST declare `disallowed_tools: "Write, Edit, MultiEdit"`.
- `bash_guard` metadata for write-capable agents (see `builder` for the canonical example).

## Adding a hook

```bash
# 1. Author hooks/recipes/<your-hook>.py with this discipline:
#    - Respect ULTRAPROMPT_DISABLE_HOOKS=1 (exit 0 if set).
#    - Fail open on stdin parse error (try/except → exit 0).
#    - Wrap ledger writes in try/except (never block tool delivery).
# 2. Register in hooks/hooks.json and hooks/hooks.windows.json under the appropriate slot:
#    SessionStart | UserPromptSubmit | PreToolUse | PostToolUse | SubagentStart | Stop | SessionEnd
# 3. Add fixtures under tests/hooks/<your-hook>/:
#    {"input": {...}, "env": {...}, "expected_exit": <int>, "expected_decision": "...", "stdout_contains": "..."}
# 4. Register in scripts/run-hook-tests.py:HOOK_TO_SCRIPT.
# 5. Run: python3 scripts/run-hook-tests.py  (all fixtures must pass)
```

## Adding an MCP tool

```python
# Edit mcp/ultraprompt_meta.py. Append to the TOOLS dict:
"my_new_tool": (
    "Description that appears in tools/list. Read-only.",
    {
        "type": "object",
        "properties": {"arg": {"type": "string"}},
    },
    tool_my_new_tool,  # handler function defined above
    {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
),
```

All 4 annotation keys (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) are required per MCP spec. The `MCP_RISK_HINTS_MISSING` lint will warn if any are absent.

```bash
python3 mcp/ultraprompt_meta.py --self-test     # must exit 0
python3 scripts/build-capability-graph.py
python3 scripts/validate-descriptions.py        # no MCP_RISK_HINTS_MISSING for your tool
```

## Validation gate (before opening a PR)

```bash
python3 scripts/validate-descriptions.py
python3 scripts/audit-catalog-consistency.py
python3 scripts/validate-plugin.py
python3 scripts/run-hook-tests.py
python3 scripts/run-router-bench.py
python3 scripts/render-manifest-template.py --check
python3 scripts/audit-catalog-counts.py
python3 scripts/release-scorecard.py
```

All must exit 0. The CI workflow at `.github/workflows/validate.yml` runs the same suite on every push and PR.

## Local testing

```bash
# Install into Claude Code:
scripts/install.sh both        # macOS / Linux
scripts/install-windows.ps1    # Windows
# Then in Claude Code: /reload-plugins
```

## Shipping a release (maintainers only)

Version lives in **one** place — the `VERSION` file. Everything else is rendered
from it or checked against it; do not hand-edit version strings in the manifests.

1. Set the new version in `VERSION` (e.g. `9.2.0`).
2. Add the matching `## [X.Y.Z] - YYYY-MM-DD` entry at the top of `CHANGELOG.md`.
3. Bump the one hand-maintained version site: `.codex-plugin/plugin.json`
   (`version` + description). The drift guard asserts it equals `VERSION`.
4. `python3 scripts/build-catalog-metadata.py && python3 scripts/build-capability-graph.py && python3 scripts/build-skill-index.py`
   (regenerates `dist/` so `plugin_version` flows through).
5. `python3 scripts/render-manifest-template.py` (renders plugin.json,
   marketplace.json, README.md, menu.md, dashboard.md from `${version}` + counts).
6. Run the validation gate above — `render-manifest-template.py --check` and
   `run-release-integrity-tests.py` will fail if any version site drifts.
7. `git commit -am "Bump ultraprompt to vX.Y.Z"`
8. `git tag vX.Y.Z -m "Ultraprompt vX.Y.Z — <one-line theme>"`
9. `git push origin main && git push origin vX.Y.Z`

## Reaching maintainers

Open an issue at https://github.com/Sokoliem/ultraprompt for design questions before sending a large PR. For small fixes (description copy, new patterns, doc updates), just open a PR.

## Code of conduct

Be kind, be specific, and assume good faith. Ultraprompt is opinionated about engineering discipline; disagreement on technical merit is welcome, personal attacks are not.
