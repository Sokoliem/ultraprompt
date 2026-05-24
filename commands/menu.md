---
description: Show the Ultraprompt V8 menu and recommend the best next routes for the current task. Auto-invokable when listing or comparing routes would help.
argument-hint: [optional: current task or goal]
---

# Ultraprompt V8 Menu

Catalog: 55 skills, 34 agents, 42 MCP tools, 33 commands, 12 panels, 17 artifact schemas.

If `$ARGUMENTS` is present, recommend the top 3 most relevant routes first. If the task is ambiguous, recommend `/ultraprompt:route $ARGUMENTS` instead of guessing.

## Core Routes

- `/ultraprompt:review` - diff/branch/PR review
- `/ultraprompt:debug` - active failure diagnosis
- `/ultraprompt:ci-repair` - build, lint, typecheck, or pipeline failure
- `/ultraprompt:build` - feature implementation
- `/ultraprompt:refactor` - behavior-preserving cleanup
- `/ultraprompt:test-harden` - write or strengthen tests
- `/ultraprompt:test-gap-analysis` - find missing coverage and edge cases
- `/ultraprompt:repo-map` - structural discovery
- `/ultraprompt:architect` - boundaries and system design
- `/ultraprompt:api-contract` - public-surface compatibility
- `/ultraprompt:migrate` - migration sequencing
- `/ultraprompt:release-readiness` - ship/no-ship readiness
- `/ultraprompt:release` - release notes and changelog
- `/ultraprompt:security-audit` - auth, secrets, injection, tenant isolation

## Specialist Routes

- `/ultraprompt:gap-analysis`
- `/ultraprompt:feature-completeness`
- `/ultraprompt:data-flow-privacy-map`
- `/ultraprompt:dependency-audit`
- `/ultraprompt:supply-chain-hardening`
- `/ultraprompt:performance-pass`
- `/ultraprompt:accessibility-review`
- `/ultraprompt:database-review`
- `/ultraprompt:infra-iac-review`
- `/ultraprompt:observability-pass`
- `/ultraprompt:ai-agent-safety-review`
- `/ultraprompt:llm-eval-design`
- `/ultraprompt:contract-test-generate`
- `/ultraprompt:state-machine-review`
- `/ultraprompt:tui-design-innovate`
- `/ultraprompt:docs-sync`
- `/ultraprompt:technical-debt-triage`

## Product And Ecosystem Routes

- `/ultraprompt:prd-lite`
- `/ultraprompt:prd-standard`
- `/ultraprompt:prd-technical`
- `/ultraprompt:prd-ai-feature`
- `/ultraprompt:prd-to-plan`
- `/ultraprompt:plugin-review`
- `/ultraprompt:skill-author`
- `/ultraprompt:agent-author`
- `/ultraprompt:hooks-design`
- `/ultraprompt:mcp-design`

## Discovery And Operations

- `/ultraprompt:route <intent>` - pick the right skill
- `/ultraprompt:why <skill>` - explain lane boundaries
- `/ultraprompt:panel-run <pattern>` - multi-perspective orchestration
- `/ultraprompt:claim-check "<draft>"` - verify a draft answer against evidence
- `/ultraprompt:repo-capsule [path]` - read-only repo contract
- `/ultraprompt:evidence-report` - validation, edits, blocks, and dispatch history
- `/ultraprompt:dashboard` - localhost catalog, health, and live activity
- `/ultraprompt:doctor` - full plugin health
- `/ultraprompt:usage [--days N]` - local-only telemetry

Keep the response compact. End with one recommended next slash-command.
