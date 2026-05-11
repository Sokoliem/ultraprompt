# CLAUDE.md Template

CLAUDE.md is the entry point an LLM agent reads before doing work in a repository. The goal: tell the agent what it cannot infer from inspection in 2-3 minutes of grep.

## Shape

```
# Project: <name>

One sentence on what this project is. Two sentences max.

## Repository conventions

- Package manager: <npm|pnpm|yarn|cargo|pip|poetry|...>
- Test runner: <jest|vitest|pytest|cargo test|...>
- Lint: <command>
- Type check: <command>
- Build: <command>

## Commands

- Test (focused): <how to run a single test by name>
- Test (full): <how to run the full suite>
- Lint + fix: <command that auto-fixes>
- Type check: <command>
- Local dev: <how to run the app locally>

## Architecture

Two paragraphs max. Top-level packages, dependency direction, what the public surface is. Diagrams live in /docs, not here.

## Conventions that are not obvious from code

- <e.g. "All async DB calls go through repository pattern under src/db/repos/">
- <e.g. "Feature flags read via useFlag(); do not import the SDK directly">
- <e.g. "Error responses must use the ApiError type; do not throw plain strings">

## Things to avoid

- <e.g. "Do not edit src/generated/* by hand; run pnpm generate">
- <e.g. "Do not bypass the auth middleware in routes; it's enforced at the gateway">

## When stuck

Point at the highest-leverage references (key files, key tests, recent ADRs).
```

## Quality bar

- Under 100 lines; if it grows, split into /docs and link
- Every command should run as-is (test the README quickstart from a clean checkout)
- "Conventions that are not obvious" is the highest-value section. If you skip it, the agent will infer wrong from neighbors
- "Things to avoid" prevents specific past failures; not generic best-practice advice

## Anti-patterns

- Restating universal best practices ("write tests"). The agent already knows.
- Listing every directory's purpose. The directory tree shows it.
- Aspirational rules that the codebase does not actually follow. Document reality, not intent.
- Changing the file every PR with minor updates; treat it as a design surface

## Maintenance

CLAUDE.md drift is silent and expensive. When a convention changes (new test runner, new lint command), the agent will follow the old one until CLAUDE.md is updated. Treat updates as part of the change that introduced the new convention.
