---
name: "design-system-review"
description: "When user says 'design system review / component library audit / token audit / theme consistency / UI consistency audit / component API design / design rules for this repo' - dispatches design-critic with design-system focus. DEFAULT for systematic frontend design-language, component-library, token, theme, and pattern-consistency reviews."
when_to_use: "Manual-only. Invoke when the concern is systemic UI consistency rather than one page: token usage, spacing and typography scales, component API ergonomics, variant sprawl, theming, density modes, icon usage, documentation drift, and governance for design rules."
argument-hint: "[design system path|component library|theme|tokens]"
tier: "specialist"
aliases: ["component-library-review", "token-review", "theme-review", "ui-consistency-audit"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Design System Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:design-critic` (focus: `design-system`) for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `experience-quality-panel`. Preferred: `experience-quality-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

A design system is a product-quality constraint system, not a folder of components. Review token semantics, component contracts, variant count, composition boundaries, state coverage, density, theming, documentation, and escape hatches. The goal is fewer one-off decisions and clearer product fit, not a prettier component zoo.

## First signals to inspect

- Token sources: CSS variables, Tailwind config, theme files, Figma variables, style dictionaries, or constants.
- Component library entrypoints: buttons, inputs, cards, tables, modals, menus, tabs, toasts, layout primitives.
- Variant and size APIs: props, class recipes, CSS modules, slot patterns, compound components.
- Theme behavior: light/dark, brand themes, density modes, high contrast, reduced motion.
- Documentation and examples: Storybook, docs pages, MDX, screenshots, usage snippets.
- Local deviations: ad hoc colors, duplicated components, one-off spacing, manual SVGs, unowned CSS overrides.

## Failure modes specific to this lane

- Treating visual consistency as only color matching.
- Adding tokens without semantics or usage rules.
- Letting variants multiply until every screen has a bespoke component.
- Ignoring interaction states and accessibility affordances in component APIs.
- Breaking existing product surfaces by enforcing a design rule without migration path.
- Reviewing generated CSS output without tracing source-of-truth tokens and components.

## Workflow

1. Map the design-system sources: tokens, themes, components, docs, examples, and consuming apps.
2. Identify semantic token coverage and ad hoc style escape hatches.
3. Review core components for state coverage, accessibility affordances, API clarity, density, and composability.
4. Find duplicated or drifted patterns and classify whether to consolidate, document, or intentionally preserve.
5. Recommend a migration sequence that avoids breaking active product surfaces.
6. Name governance checks: lint rules, visual snapshots, docs examples, story coverage, or design-rule files.

## Validation

Validate findings against source-of-truth token/component files and at least two consuming surfaces. For fixes, run component tests or Storybook/visual snapshots where available, plus a targeted search for removed token/component names.

## Output contract

Design-system map | Token semantics findings | Component API findings | State/a11y coverage findings | Drift/duplication findings | Migration sequence | Governance checks | Validation commands

## Subagent delegation

Dispatch design-critic by default. Escalate to experience-quality-panel for broad UI systems that need independent a11y, implementation, and test strategy review.

## V4 aliases

This skill answers to V4 names: `component-library-review`, `token-review`, `theme-review`, `ui-consistency-audit`. The router resolves them to `design-system-review` and notes the alias in its response.
