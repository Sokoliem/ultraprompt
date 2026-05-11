---
description: Check for model, effort, long-context, or extra-usage runtime pins in the Ultraprompt plugin.
disable-model-invocation: true
argument-hint: [optional: plugin path]
---

# Cost Audit

Verify that Ultraprompt does not pin runtime profile (model, effort, long-context, extra-usage) — those should be inherited from the active session.

Run:

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit-runtime-budget.py"`

Report:

- Frontmatter files checked
- Text files checked
- Warnings (pins that should not be there)
- Errors (forbidden pins per V8 runtime-neutral policy)

If the audit is clean, the plugin is runtime-neutral. The active session controls the runtime profile for all skills and subagents.
