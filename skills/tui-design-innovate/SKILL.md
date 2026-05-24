---
name: "tui-design-innovate"
description: "**DEFAULT for terminal-UI design work: dispatches reviewer/architect with TUI design focus (information density, keyboard nav, color, layout, state): runs the tui-design-innovate discipline.**"
when_to_use: "Manual-only. Invoke for TUI app or framework work: terminal-native interaction, focus management, layout, rendering, input routing, framework primitives. Do not default to browser/desktop GUI assumptions."
argument-hint: "[surface|framework|interaction]"
tier: "specialist"
aliases: ["tui-design-innovate"]
disable-model-invocation: true
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# TUI Design + Innovate

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

The terminal is a native interaction medium with its own affordances: keyboard-first, character grid, persistent state, streaming output. TUI design is not 'GUI minus the mouse'. Think in command palettes, multi-key chords, panes, overlays, focus graphs, deterministic snapshots, and reusable framework primitives.

## First signals to inspect

- TUI framework: Textual, Ratatui, Bubbletea, blessed, Ink, custom (e.g., Celestial)
- Layout primitives: panes, splits, overlays, modals, drawers
- Focus graph: where can focus go, what's the keyboard map
- Input handling: chord support, vim-style modes, escape-from-anywhere
- Rendering: full redraw vs partial; flicker; resize handling
- Unicode + grapheme cluster handling, width calculation, truncation
- Themes, colors, semantic styles, terminal capability detection

## Failure modes specific to this lane

- Designing flows that need the mouse
- Single-pane app where multi-pane would compose better
- No keyboard map cheat sheet (users can't discover what's possible)
- Focus trap with no escape
- Resize breaks layout (layout assumed fixed dimensions)
- Wide-character / emoji breaks width calculation
- Theme that fails on light terminal background
- Streaming output that scrolls past faster than user can read

## Workflow

1. Identify the surface: full app, framework primitive, specific flow.
2. Map the keyboard interaction model: modes, chords, escape paths.
3. Design the layout: pane structure, focus graph, overlay strategy.
4. Handle terminal realities: resize, Unicode, terminal capability differences.
5. Build reusable framework primitives over one-off screens.
6. Add deterministic snapshot tests for layout.
7. Add state-machine tests for focus and input routing.

## Validation

Snapshot tests of rendered layout at various terminal sizes. State-machine tests for focus transitions. Manual test on multiple terminals (kitty, alacritty, iTerm, Windows Terminal). Test with screen reader where applicable.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Surface
    type: section
    required: true
    evidence_rule: "none"
  - field: Keyboard Interaction Model
    type: section
    required: true
    evidence_rule: "none"
  - field: Layout + Focus Graph
    type: section
    required: true
    evidence_rule: "none"
  - field: Terminal Reality Handling
    type: section
    required: true
    evidence_rule: "none"
  - field: Framework Primitives
    type: section
    required: true
    evidence_rule: "none"
  - field: Tests Added
    type: section
    required: true
    evidence_rule: "test name + run command + result"
  - field: Cross-Terminal Notes
    type: section
    required: true
    evidence_rule: "none"
```

Surface | Keyboard Interaction Model | Layout + Focus Graph | Terminal Reality Handling | Framework Primitives | Tests Added | Cross-Terminal Notes

## Subagent delegation

Dispatch `reviewer` with focus=architecture for framework structure. See `_shared/playbooks/frontend-ux-checklist.md` for general UX overlap.

## V4 aliases

This skill answers to V4 names: `tui-design-innovate`. The router resolves them to `tui-design-innovate` and notes the alias in its response.
