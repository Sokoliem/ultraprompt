---
name: "frontend-visual-qa"
description: "When user says 'visual QA / screenshot QA / responsive review / frontend polish pass / inspect this page in browser / verify the UI after changes / pixel check this surface' - dispatches design-critic with rendered-evidence focus and escalates to the experience-quality panel for deep budgets. DEFAULT for frontend quality work that must inspect actual rendered output, screenshots, responsive breakpoints, or interactive states."
when_to_use: "Use when the work needs browser-visible evidence: local routes, screenshots, responsive breakpoints, canvas/nonblank checks, visual overlap, text clipping, hover/focus/loading/error states, or before/after UI verification. Prefer design-review for pure critique without runtime verification; prefer accessibility-review for WCAG-only work."
argument-hint: "[route|component|screenshot path|viewport list]"
tier: "core"
aliases: ["visual-qa", "screenshot-qa", "frontend-polish", "responsive-qa"]
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Frontend Visual QA

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:design-critic` (focus: `visual-qa`) for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `experience-quality-panel`. Preferred: `experience-quality-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Frontend quality is observable behavior. A passing typecheck does not prove that text fits, controls are discoverable, panels do not overlap, icons render, canvases are nonblank, or responsive layouts preserve hierarchy. Use screenshots and browser probes to separate implementation truth from code-shaped intent.

## First signals to inspect

- How to run the app or component surface: dev server command, route, Storybook, static HTML, or file URL.
- Target viewports and devices: narrow mobile, tablet, desktop, wide desktop, high-DPI, and reduced-motion if relevant.
- Critical states: empty, loading, error, disabled, selected, hover, focus, modal open, sidebar collapsed, dense data loaded.
- Known design system primitives: button, card, table, tabs, menu, icon library, theme tokens, breakpoints.
- Visual failure patterns: overlapping text, clipping, shifting layout, weak contrast, inconsistent icon sizing, blank media/canvas.
- Existing visual test tools: Playwright screenshots, Storybook test runner, Percy/Chromatic, image snapshots, Lighthouse.

## Failure modes specific to this lane

- Claiming a UI is fixed after unit tests without opening or screenshotting the surface.
- Checking only one viewport for a responsive surface.
- Ignoring hover, focus, disabled, loading, and error states that users actually hit.
- Approving visual changes with hidden text clipping or control overlap.
- Treating a screenshot as success when assets, icons, or canvas pixels are blank.
- Applying broad redesigns instead of localized fixes for verified visual defects.

## Workflow

1. Find the actual frontend entrypoint, run command, route, and component ownership.
2. Start or reuse the local dev server only when needed, then inspect the real rendered surface.
3. Capture screenshots or browser evidence across the relevant desktop and mobile viewports.
4. Probe interactive states that screenshots alone miss: hover, focus, open menus, modals, loading, and errors.
5. Apply localized fixes for verified defects while preserving the design system and existing product density.
6. Re-run screenshots or visual checks and report before/after evidence plus any remaining visual risk.

## Validation

Use actual rendered evidence whenever a local surface is available. For web apps, prefer browser or Playwright screenshots at representative viewports, plus targeted assertions for text clipping, overlap, nonblank media/canvas, and expected state visibility. If runtime cannot be launched, state the exact blocker and fall back to code review only.

## Output contract

Surface + run command | Viewports/states inspected | Screenshot/browser evidence | Visual defects found | Fixes applied or proposed | Before/after verification | Remaining visual risks | Follow-up test coverage

## Subagent delegation

Default: dispatch design-critic for rendered visual critique. On deep budget, use experience-quality-panel so design, a11y, implementation, and test strategy are reviewed independently.

## V4 aliases

This skill answers to V4 names: `visual-qa`, `screenshot-qa`, `frontend-polish`, `responsive-qa`. The router resolves them to `frontend-visual-qa` and notes the alias in its response.
