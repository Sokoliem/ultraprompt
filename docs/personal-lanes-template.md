# Personal lanes template — `~/.claude/ultraprompt-user.md`

Copy the body below to `~/.claude/ultraprompt-user.md` and edit. The
`session-bootstrap` hook injects this file's contents at session start so
your personal dispatch biases become the first arbitration signal — ahead of
generic routing.

The file is plain Markdown. Keep it terse (the hook truncates at
`personal_lanes.max_chars`, default 4000). Lead with biases the model should
apply *before* falling back to the generic V8 dispatch table.

---

## Routing biases

- **Card services / TFCU work** — prefer `anthropic-skills:card-services-pm`,
  `anthropic-skills:card-services-report`, `anthropic-skills:tfcu-letter-system`
  before any ultraprompt skill considers itself relevant. Use
  `/ultraprompt:repo-capsule` first for unfamiliar code in this lane.
- **Celestial / agentic coding** — when the prompt mentions a Celestial package
  name (`nebula`, `constellation`, etc.) or the `celestial` / `celestui`
  worktree is active, dispatch the celestial prompter skill first; fall back to
  `/ultraprompt:architect` for cross-package design.
- **Frontend artifacts** — prefer `anthropic-skills:artifact-studio` or
  `anthropic-skills:frontend-studio` over `/ultraprompt:build` when the
  deliverable is a UI artifact. Use `/ultraprompt:build` only for backend or
  pure-logic code.

## Output discipline

- Default output style: **evidence-led** — Conclusion → Reasoning → Next action.
  Cite file:line whenever asserting a fact about the code.
- For diff/PR reviews: switch to **concise-review** — severity-ranked findings,
  no preamble.

## Dispatch defaults that override the generic V8 table

| Pattern | Use instead |
|---|---|
| Whole-repo audit on Celestial repo | `/ultraprompt:repo-review --deep` |
| TFCU policy or letter draft | `anthropic-skills:tfcu-letter-system` |
| UI artifact deliverable | `anthropic-skills:artifact-studio` |
| Anything multi-perspective on a Celestial release | `/ultraprompt:panel-run review-fanout` |

## Hard nos

- Never auto-run `/ultraprompt:wip-prune` without confirmation.
- Never enable dream-job auto-apply.
