---
name: "design-review"
description: "When user says 'design review / taste pass / aesthetic review / make this UI feel better / visual polish review / product design critique / does this look professional' - dispatches design-critic for evidence-backed visual and interaction critique. DEFAULT for broad product-design, taste, and aesthetic review where the expected output is a ranked critique rather than immediate implementation."
when_to_use: "Use when the user wants judgment on visual quality, product fit, hierarchy, information density, interaction polish, or whether a UI feels professional for its domain. Prefer frontend-visual-qa when the request specifically asks for screenshots, responsive checks, or browser verification; prefer accessibility-review when WCAG/a11y is the named concern."
argument-hint: "[surface|screenshot|route|component|design brief]"
tier: "core"
aliases: ["taste-review", "aesthetic-review", "product-design-review", "visual-design-review"]
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Design Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:design-critic` (focus: `design-review`) for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `experience-quality-panel`. Preferred: `experience-quality-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Good UI judgment is not generic prettiness. Review the surface against the user, domain, task frequency, information density, visual hierarchy, affordances, motion, copy tone, and brand/product signal. Operational tools should usually be dense and calm; editorial or game surfaces can carry more expressive treatment. Evidence must come from code, screenshots, design assets, or rendered behavior, not taste slogans.

## First signals to inspect

- Actual rendered surface: screenshot, local route, Storybook story, Figma frame, or component markup.
- Product domain and target user: internal operations, SaaS, consumer, developer tool, game, portfolio, marketing, or data workspace.
- Design system constraints: tokens, component library, spacing scale, icon library, theme, density conventions.
- Primary workflow: what users need to scan, compare, decide, edit, or recover from.
- Visual hierarchy: what draws first attention, what should be secondary, and what is competing.
- Interaction affordances: hover, focus, active, loading, empty, error, disabled, and responsive states.
- Content tone: labels, headings, table density, command wording, and whether text helps or clutters.

## Failure modes specific to this lane

- Giving generic advice such as "modernize the UI" without concrete evidence.
- Optimizing for decorative novelty when the product needs repeated operational use.
- Treating screenshots as final truth without checking responsive states or implementation constraints.
- Ignoring the existing design system and creating one-off visual language.
- Confusing accessibility compliance with overall product taste, or vice versa.
- Recommending large visual rewrites without a prioritized sequence and validation path.

## Workflow

1. Identify the surface, audience, product category, and design-system constraints.
2. Collect visual evidence from screenshots, local browser, component stories, or relevant code.
3. Assess hierarchy, layout, density, contrast, rhythm, copy, affordances, and state coverage.
4. Compare the surface to the domain expectation: operational, editorial, game, marketing, developer tool, or data workspace.
5. Rank findings by user impact and implementation leverage, separating must-fix polish from taste preferences.
6. Recommend follow-up routes: frontend-visual-qa for rendered verification, design-system-review for systemic drift, accessibility-review for WCAG issues, or build for implementation.

## Validation

Read-only review. Validate by tying every finding to a screenshot, route, component, token, or file reference. For implementation follow-up, require visual regression evidence or before/after screenshots across at least desktop and mobile when the surface is responsive.

## Output contract

Scope + evidence reviewed | Product/domain fit verdict | Visual hierarchy findings | Layout + density findings | Interaction/state findings | Copy/tone findings | Design-system alignment | Ranked recommendations | Follow-up validation plan

## Subagent delegation

Default: dispatch design-critic for the critique. Escalate to experience-quality-panel when the surface is high-stakes, cross-platform, or needs independent a11y/test/design perspectives.

## V4 aliases

This skill answers to V4 names: `taste-review`, `aesthetic-review`, `product-design-review`, `visual-design-review`. The router resolves them to `design-review` and notes the alias in its response.
