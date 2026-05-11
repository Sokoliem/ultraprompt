---
name: "accessibility-review"
description: "When user says 'a11y review / accessibility audit / WCAG check / screen reader compatibility / keyboard navigation review / color contrast audit / accessible component review' — dispatches auditor with a11y focus. DEFAULT for accessibility audits."
when_to_use: "Manual-only. Invoke for a11y-focused review of UI components, flows, or design-system fit. For general frontend review, see `_shared/playbooks/frontend-ux-checklist.md`."
argument-hint: "[component|flow|page]"
tier: "specialist"
aliases: ["accessibility-review"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Accessibility Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:auditor` (focus: `a11y`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

WCAG provides the framework but not the answers. Screen reader experience, keyboard navigation, focus management, color contrast, and motion sensitivity are independent axes that all need to work. Automated tools (axe, Lighthouse) catch ~30% of issues; the rest requires manual testing or expert review.

## First signals to inspect

- Component library or design system; any a11y conventions documented
- Existing automated a11y testing (axe-core, jest-axe, Lighthouse CI)
- Semantic HTML usage (real buttons, real links, headings, landmarks)
- ARIA usage (often misused; semantic HTML usually wins)
- Focus order and visible focus indicators
- Keyboard navigation paths (Tab, Shift+Tab, arrow keys, Escape, Enter)
- Color contrast ratios on text and interactive elements

## Failure modes specific to this lane

- Adding ARIA roles to non-semantic elements when a real button/link would work
- Visible focus indicator removed for aesthetics (`:focus { outline: none }` without replacement)
- Keyboard trap in modals (no Escape, no focus management)
- Form errors announced visually but not to screen readers
- Click handlers on non-interactive elements (div with onclick)
- Color as the only signal (red text without an icon or label)

## Workflow

1. Inventory the components/flows in scope.
2. Run automated tools (axe, Lighthouse) for low-hanging fruit.
3. Test keyboard navigation: can every interactive element be reached and activated by keyboard alone?
4. Test focus management: where does focus go when modals open/close, errors appear, content updates?
5. Test screen reader: does each control announce its role, name, and state?
6. Check contrast on text and interactive elements.
7. Apply fixes; verify with the same tests.

## Validation

Re-run automated tools. Manual keyboard test of changed flows. Manual screen reader test (NVDA, VoiceOver, JAWS) on critical paths.

## Output contract

Scope | Automated Findings | Keyboard Navigation Findings | Focus Management Findings | Screen Reader Findings | Contrast Findings | Fixes Applied | Remaining Issues

## Subagent delegation

Dispatch `auditor` with focus=a11y for second perspective. See `_shared/playbooks/frontend-ux-checklist.md` for broader UX review.

## V4 aliases

This skill answers to V4 names: `accessibility-review`. The router resolves them to `accessibility-review` and notes the alias in its response.
