---
description: Explain when an Ultraprompt skill is the right fit, when not to use it, and what adjacent alternatives exist.
disable-model-invocation: true
argument-hint: <skill name or problem>
---

# Why this skill?

Explain when `$ARGUMENTS` is the right fit. If `$ARGUMENTS` is a skill name (or V4 alias), explain that skill. If it's a problem, name the best skill and explain why.

Preferred path:

1. If the `ultraprompt-meta` MCP server is available, call `explain_skill` with the skill name.
2. Otherwise, read frontmatter from `${CLAUDE_PLUGIN_ROOT}/skills/<name>/SKILL.md`.
3. Resolve legacy aliases to current skill names; note the alias.

For each skill, return:

- **Use when**: the conditions where this skill is the correct lane
- **Don't use when**: adjacent cases where a different skill is better
- **Adjacent alternatives**: the 1-2 most relevant other skills, with the boundary
- **Tier**: core / specialist / ecosystem (auto-discoverable vs manual-only)
- **Aliases**: V4 names that resolve here

Keep the response under 20 lines. The goal is to help the user pick fast, not to write documentation.
