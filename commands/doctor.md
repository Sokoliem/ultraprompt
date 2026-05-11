---
description: Validate the Ultraprompt V8 plugin and report generated artifacts, catalog metadata, skill, agent, hook, MCP, evidence, routing, telemetry, and duplication health.
disable-model-invocation: true
argument-hint: [optional: plugin path]
---

# Ultraprompt Doctor (V8)

Validate the Ultraprompt plugin package. Default target is `${CLAUDE_PLUGIN_ROOT}`. If `$ARGUMENTS` is a path, use that.

Run, in order. Continue on failures and summarize all results at the end.

1. Build/check the generated skill index:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build-skill-index.py" --check`
2. Verify skills regenerate identically from specs:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/regenerate-skills.py" --check`
3. Verify agents regenerate identically from specs:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/regenerate-agents.py" --check`
4. Build/check catalog metadata:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/build-catalog-metadata.py" --check`
5. Run catalog consistency audit:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-catalog-consistency.py"`
6. Run plugin validator:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/validate-plugin.py"`
7. Run manifest schema audits:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-manifest-schemas.py" --runtime claude-code`
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-manifest-schemas.py" --runtime codex`
8. Run runtime-budget audit:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-runtime-budget.py"`
9. Run skill-tier audit:
   - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-skill-tiers.py"`
10. Run duplication audit:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-duplication.py"`
11. Run router bench:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-router-bench.py"`
12. Run adversarial router cases:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-router-bench.py" --adversarial`
13. Run catalog overlap budget:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-router-bench.py" --overlap-budget`
14. Run hook fixtures:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-hook-tests.py"`
15. Run hook coverage matrix:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-hook-coverage.py"`
16. Run config and artifact regression tests:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-config-tests.py"`
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run-artifact-tests.py"`
17. Smoke-test MCP server:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/mcp/ultraprompt_meta.py" --self-test`
18. Show legacy evidence-ledger path and recent record count:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-ledger.py" path`
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-ledger.py" report` (head only)
19. Dispatch outcomes:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor-dispatch-outcomes.py" 7`
20. Skill activation scorecard:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/doctor-skill-activation.py" 7`
21. Ledger v2 summary:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py" path`
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/ledger-v2.py" summary --days 7`
22. Catalog robustness audit:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/catalog-audit.py"`
23. Artifact schema list:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artifact-validate.py" schemas`
24. Install manifest verify:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/install-manifest.py" verify "${CLAUDE_PLUGIN_ROOT}"`
25. Release scorecard:
    - `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/release-scorecard.py"`

If `python3` is unavailable, retry with `python`.

After all checks, summarize pass/fail per check. For V8 specifically report:

- Catalog metadata freshness.
- Generated skill and agent drift.
- Hook fixture result and hook coverage matrix coverage.
- Config env override test status.
- Artifact enum validation test status.
- Plugin specialist dispatch share.
- Never-fired specialist agents.
- skill_invocation count vs. agent_dispatch count.
- mcp_tool_call top tools.
- wip_save count.

The highest-leverage fixes go at the top. If the ledger shows 0 skill_invocation events and the user has been working actively for 24h+, flag telemetry or routing activation as a likely issue.

Diagnostic only: no plugin files are rewritten.
