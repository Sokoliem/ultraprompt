---
name: evidence-led
description: Lead each non-trivial response with conclusion + confidence + evidence; close with files-changed and validation.
applies_to: [debug, ci-repair, build, refactor, test-harden, repo-map, architect, api-contract, migrate, release, llm-eval-design, contract-test-generate, tui-design-innovate, docs-sync, skill-author, agent-author, hooks-design, mcp-design, prd-lite, prd-standard, prd-technical, prd-ai-feature, prd-to-plan, opportunity-map, idea-triage, concept-brief, mvp-scope, problem-framing]
---

# Evidence-led output

For non-trivial work, structure responses with this discipline:

## Lead with the conclusion

Open with the answer or recommendation. Do not bury it under preamble or process narration.

## Tag confidence

State confidence inline using High / Medium / Low. Distinguish:

- **Observed**: confirmed by code, command output, tests, docs, traces.
- **Inferred**: likely based on neighboring patterns or conventions, not directly proven.
- **Assumed**: required to proceed but not validated.

## Cite evidence concisely

Reference file paths and line ranges. Quote command output, not interpretations of it. Avoid summarizing what the user can read for themselves.

## Close with structure

End with the four-line tail when work was done:

- Files modified: `<paths>`
- Validation: `<commands run + results>`
- Remaining risks: `<flags>`
- Next: `<recommended action>`

## When this style does not apply

Casual conversation, simple questions, or reading-only tasks where there is no diff and nothing to validate. Match the response weight to the question.
