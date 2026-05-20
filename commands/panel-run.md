---
description: V8. Run a coordinated expert panel with structured phase contracts, cognitive policy metadata, parallel agent dispatch, and synthesis. Available panels include repo, feature, contract, release, product, AI, idea, MVP, governance, security/privacy, migration, and incident-response panels.
argument-hint: <panel-name> [scope]
---

# Panel Run (V8)

Run a precomposed expert panel against the current repo or a named scope.

## Available panels

Call the `panel_plan` MCP tool without arguments to list panels with cost, risk, mode, confirmation, and use-when criteria.

| Panel | Mode | Risk | Agents | When to use |
|---|---|---|---:|---|
| `repo-completeness-panel` | read-only | medium | 8 | Whole-repo audit, all dimensions covered |
| `feature-gap-panel` | read-only | low | 5 | One named feature E2E |
| `contract-drift-panel` | read-only | medium | 4 | API/schema/event/config drift suspected |
| `release-gate-panel` | read-only | high | 6 | Pre-release ship/no-ship decision |
| `prd-panel` | proposal-only | medium | 5 | Full PRD with technical, measurement, and risk review |
| `ai-feature-panel` | proposal-only | high | 6 | AI/LLM feature spec with eval, safety, and controls |
| `idea-panel` | proposal-only | low | 5 | Early-stage idea generation and validation |
| `mvp-panel` | proposal-only | medium | 4 | MVP scope, feasibility, and validation plan |
| `cognitive-governance-panel` | proposal-only | medium | 6 | Memory, learning, dream, dashboard, graph, and pathfinder health |
| `security-privacy-panel` | read-only | high | 6 | Security, privacy, data-flow, and controls review |
| `migration-readiness-panel` | read-only | high | 6 | Migration readiness, compatibility, rollout, and test gates |
| `incident-response-panel` | read-only | high | 6 | Incident triage, impact, recovery, and postmortem scaffold |

## Execution

1. Parse `$ARGUMENTS` for `<panel-name> [scope]`. If no panel name: call `panel_plan` MCP tool with no args, print catalog, ask user which panel.
2. Call `panel_plan` MCP tool with `panel_name` and optional `scope`. Receive phased dispatch plan, inputs, success criteria, handoff artifacts, risk, confirmation, cognitive policies, and phase contracts.
3. Start a resumable lifecycle record with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/panel-runs.py start --panel <panel-name> --scope <scope>`. Keep the returned `run_id`.
4. Execute phases in order:
   - **Sequential phases (`parallel=false`):** dispatch the single agent, wait for completion, pass output as context to next phase.
   - **Parallel phases (`parallel=true`):** issue all Task calls in a single assistant message. Wait for all to complete before proceeding.
5. Before and after each phase, update lifecycle state with `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/panel-runs.py update <run_id> --phase <phase> --phase-status <running|completed|failed>`.
6. After synthesize phase: present the final structured artifact to the user and record artifact/validation paths on the run.
7. If panel `writes_gap_ledger=true` and synthesis produced gap entries, write them via the `gap_ledger_write` MCP tool and include `panel_run_ids: [<run_id>]`.

## Synthesis pattern

For panels with multiple parallel auditors, the synthesis-phase agent receives:

- Repo map or phase-specific input from earlier phases
- Each parallel auditor's structured output
- The panel's success criteria, handoff artifacts, cognitive policies, and quality gates
- Instruction to dedupe, reconcile severity, sequence implementation, and preserve confirmation boundaries

The user receives the synthesized artifact, not the raw individual outputs. Raw outputs go to the evidence ledger for traceability.

## Cost and confirmation

Before running panels, follow the panel's `confirmation.required` field. For high-risk panels, also name the risk even when confirmation is not required:

> "This will dispatch 8 agents in 3 phases (~25 min, high cost, medium risk). Proceed?"

For medium-cost panels, mention the agent count, phase count, and whether the panel is read-only or proposal-only.

## Backwards compatibility

Legacy `team_plan` MCP tool name remains callable as an alias for `panel_plan`.
