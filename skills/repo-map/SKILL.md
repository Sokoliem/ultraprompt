---
name: "repo-map"
description: "**DEFAULT for REPO DISCOVERY & CODE LOCATION — structured read-only repo contract you cache before any implementation, review, onboarding, or planning work: cached read-only repo contract: architecture, packages, workflows, validation commands, conventions, dependencies, ownership, sensitive paths, recent activity, plus `--semantic` code search for finding code by behavio....** Different from /repo-review (audits the whole repo, this maps it), /architect (design decisions, not discovery), built-in Explore (unstructured tour without caching or validation-command surfacing). Triggers: 'find code that does X, where is the code for Y, find the handler for Z, locate the function that handles W, code search, semantic search, onboarding to this repo, give me a repo map, what's in this repo, how is this repo organized'."
when_to_use: "Use when you need to understand a repository quickly before doing implementation, review, onboarding, migration, or planning work. Use `--onboarding` for new-contributor framing. Use `--semantic <query>` to find code by behavior or natural-language concept."
argument-hint: "[path|focus area|--onboarding|--semantic <query>]"
tier: "core"
aliases: ["repo-map", "onboarding-map", "semantic-search-codebase"]
output_style: "evidence-led"
allowed-tools: "Read, Grep, Glob, Bash, Agent"
---

# Repo Map

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:scout`. See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Distinctive judgment

Structural discovery, not architectural judgment. Map what is, not what should be. The output is a working guide for another agent or contributor to act on. Prefer the cached `repo_capsule` MCP tool when available; supplement with grep/glob for the specific question.

## First signals to inspect

- Top-level layout: src/, packages/, apps/, scripts/, tests/, docs/
- Package manifests and lockfiles (single-package vs monorepo)
- Build/test/lint/typecheck commands (package.json scripts, Makefile, CI workflows)
- Entrypoints (main, bin, exports, app/index)
- Generated files and conventions (often hint at framework choices)
- CLAUDE.md, AGENTS.md, CONTRIBUTING.md, .cursorrules

## Failure modes specific to this lane

- Treating directory names as authoritative (a folder named 'core' may not contain core logic)
- Missing package boundaries in monorepos
- Reading source as ground truth when generated code or schemas drive it
- Producing an unreadably exhaustive map instead of a working guide
- Re-discovering what `repo_capsule` already cached

## Workflow

1. Call `repo_capsule` MCP tool first if available; check cache.
2. Identify repo shape: packages, entrypoints, build/test commands, configs, CI, generated files, docs.
3. Map subsystems, dependency directions, public surfaces, common workflows.
4. Identify hotspots: brittle areas, undocumented conventions, onboarding blockers.
5. If `--semantic <query>`: locate code matching the conceptual query (grep across implementation + adjacent tests/docs).
6. If `--onboarding`: frame for a new contributor (where to read first, what to install, how to run things).
7. Produce a concise navigable map. Stay read-only.

## Validation

Read-only skill. No code changes. Validate the map by running the inferred commands (build, test, lint) — confirm they work.

## Output contract

Schema below + `${CLAUDE_PLUGIN_ROOT}/_shared/OUTPUT-CONTRACT.md` + `evidence-led` style.

```yaml
schema:
  - field: Executive Overview
    type: section
    required: true
    evidence_rule: "none"
  - field: Directory/Package Map
    type: section
    required: true
    evidence_rule: "none"
  - field: Primary Workflows + Commands
    type: section
    required: true
    evidence_rule: "command + exit code + excerpt"
  - field: Architecture Sketch
    type: section
    required: true
    evidence_rule: "none"
  - field: Public APIs
    type: section
    required: true
    evidence_rule: "none"
  - field: Test/Validation Map
    type: section
    required: true
    evidence_rule: "exact commands run + exit codes + stdout/stderr excerpts"
  - field: Conventions Inferred
    type: section
    required: true
    evidence_rule: "none"
  - field: Hotspots/Questions
    type: section
    required: true
    evidence_rule: "none"
  - field: Best Next Commands
    type: section
    required: true
    evidence_rule: "command + exit code + excerpt"
```

Executive Overview | Directory/Package Map | Primary Workflows + Commands | Architecture Sketch | Public APIs | Test/Validation Map | Conventions Inferred | Hotspots/Questions | Best Next Commands

## Subagent delegation

Use `scout` for a fresh-context structural sweep when the repo is large or unfamiliar. Use `auditor` with focus=infra for IaC/deployment specifics.

## V4 aliases

This skill answers to V4 names: `repo-map`, `onboarding-map`, `semantic-search-codebase`. The router resolves them to `repo-map` and notes the alias in its response.
