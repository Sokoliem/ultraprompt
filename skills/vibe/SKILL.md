---
name: "vibe"
description: "**DEFAULT for VIBE CODING — surface 4–8 prompt-path options across 2–4 lanes via a two-stage AskUserQuestion picker, then expand the selected seed into a full detailed prompt: dispatches the `vibe-curator` agent to produce a typed `prompt_path_set.v1` artifact, runs lane-pick → path-pick via AskUserQuestion, and drafts a ready-to-run prompt from the chosen seed.** Different from /choose (routes an existing intent to an existing skill — this generates new intent options), /idea-triage (ranks pre-supplied ideas — this generates them), /innovation-lead (long-form ideas without picker UX or per-path seeds). Triggers: 'vibe with me, vibe coding, what should I build, not sure what to work on, help me explore options, kicking around ideas, give me some directions, show me what I could build'."
when_to_use: "Use when the user has open-ended coding intent and would benefit from picking between concrete next-step paths before committing. Auto-invoked by the vibe-detect UserPromptSubmit hook when vibe phrases are detected; manually invokable as `/ultraprompt:vibe [optional intent]`. Do not use when the intent is already specific (use /build, /refactor, /debug) or when you need product ideation outside a coding repo (use /innovation-lead)."
argument-hint: "[optional intent — empty for repo-scan]"
tier: "core"
aliases: ["vibe-coding", "pick-direction"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Vibe

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:vibe-curator` for the analysis phase only. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Generation is dispatched off the main thread; the orchestrator only runs the two-stage picker and the expansion step. AskUserQuestion's hard 4-option cap is honored by grouping the curator's paths into lanes for stage 1 and showing ≤4 paths per lane in stage 2. The expanded prompt is surfaced for the user to approve or invoke — it is never auto-executed.

## First signals to inspect

- User intent from `$ARGUMENTS` or the inline directive payload from the vibe-detect hook
- Repo scan signals available to vibe-curator (README, CHANGELOG, TODOs, recent dirs)
- Output of `Task(subagent_type='vibe-curator', ...)` — a `prompt_path_set.v1` YAML artifact
- `mcp__plugin_ultraprompt_ultraprompt-meta__artifact_validate` result on the artifact

## Failure modes specific to this lane

- Trying to fit >4 options into one AskUserQuestion panel — always use the two-stage lane→path split when paths span ≥2 lanes
- Skipping the artifact_validate gate and surfacing an invalid curator artifact to the picker
- Auto-invoking the selected expansion (running /build immediately) — surface the expanded prompt; let the user decide to invoke
- Showing a stage-1 lane panel when only 1 lane has paths — collapse to a single stage-2 panel in that case
- Failing to log path/lane selection telemetry — the learning queue depends on these events
- Stuffing the full expanded prompt into the curator's `seed` field — the seed is a directive, the expansion is the skill's job

## Workflow

1. Resolve intent from `$ARGUMENTS` or the inline directive payload. If empty, note 'repo-scan mode' for the curator.
2. Dispatch `Task(subagent_type='vibe-curator', description='Generate vibe paths', prompt=<intent + repo context hint>)`.
3. Receive the curator's YAML artifact. Call `mcp__plugin_ultraprompt_ultraprompt-meta__artifact_validate` against the `prompt_path_set.v1` schema. On failure, surface the validation error and abort (do not show a half-baked picker).
4. Group paths by lane. If ≥2 lanes have paths, run `AskUserQuestion` (stage 1): up to 4 lane options, each with a preview listing the top 1–2 path labels in that lane. If only 1 lane, skip stage 1.
5. Run `AskUserQuestion` (stage 2): up to 4 paths within the chosen lane, each option's preview = the path's `preview` + a one-line risk/confidence tag. Cap at 4 by confidence-descending if needed.
6. Expand the selected path: take the user's original intent + the path's `seed` + `rationale` + `expected_files`, and draft a full, detailed prompt in evidence-led style. The expanded prompt should be ready to paste into a fresh agent invocation.
7. Surface the expanded prompt to the user. Do not auto-execute it; offer the matching follow-up skill (`/ultraprompt:build`, `/ultraprompt:refactor`, etc.) based on the chosen lane.
8. Log telemetry: `vibe_paths_generated` (after curator), `vibe_lane_picked` (after stage 1), `vibe_path_picked` (after stage 2), `vibe_prompt_drafted` (after expansion). Use `scripts/ledger-v2.py:write_event`, matching the pattern in `hooks/recipes/user-prompt-route-suggest.py`.

## Validation

Behavioral. Verify: (a) vibe-curator was dispatched and returned a schema-valid artifact; (b) lane and path AskUserQuestion panels were shown (or stage 1 was correctly skipped when only one lane had paths); (c) the expanded prompt was produced and surfaced; (d) telemetry events were written. The skill writes no files; success is the user receiving an expanded prompt or explicitly cancelling.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Original Intent
    type: section
    required: true
    evidence_rule: "verbatim user prompt or 'repo-scan mode'"
  - field: Generation Trigger
    type: section
    required: true
    evidence_rule: "hook directive | manual invocation"
  - field: Curator Artifact Summary
    type: section
    required: true
    evidence_rule: "lane counts + path count + artifact_validate result"
  - field: Lane Choice
    type: section
    required: false
    evidence_rule: "chosen lane name (omit if stage 1 was skipped)"
  - field: Path Choice
    type: section
    required: true
    evidence_rule: "chosen path label + fingerprint"
  - field: Expanded Prompt
    type: section
    required: true
    evidence_rule: "full drafted prompt, ready to paste"
  - field: Suggested Follow-up Skill
    type: section
    required: true
    evidence_rule: "ultraprompt skill best matching the chosen lane"
  - field: Telemetry Events Written
    type: section
    required: true
    evidence_rule: "list of ledger event names written"
```

Original Intent | Generation Trigger (hook directive | manual) | Curator Artifact Summary (lane counts + path count) | Lane Choice (if stage 1 shown) | Path Choice | Expanded Prompt | Suggested Follow-up Skill | Telemetry Events Written

## Subagent delegation

Default dispatch target is `vibe-curator` for the generation phase. The orchestration phases (picker, expansion) run inline in the main thread because they are interactive (AskUserQuestion).

## V4 aliases

This skill answers to V4 names: `vibe-coding`, `pick-direction`. The router resolves them to `vibe` and notes the alias in its response.
