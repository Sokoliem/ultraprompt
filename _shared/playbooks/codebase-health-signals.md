# Codebase Health Signals

Health signals are observable proxies for the dimensions that determine how easy or painful the codebase is to work in. Triangulate; no single signal is conclusive.

## Change-friction signals

- **PR cycle time**: time from PR open to merge. Long cycles often mean tangled boundaries or weak CI signals.
- **Files-per-PR distribution**: PRs that consistently touch 30+ files often indicate boundary problems or codegen drift.
- **Revert rate**: PRs reverted within 7 days. Above 5% is a smell.
- **Hot files**: files in the top 5% of churn. Often correlate with bug density and ownership confusion.

## Quality signals

- **Test runtime**: full suite duration locally and in CI. Above 10 minutes locally erodes the test-driven habit.
- **Flake rate**: % of CI runs that fail and pass on retry. Above 1% is a problem.
- **Coverage on changed lines**: tracks whether new code is tested, separate from total coverage.
- **Type-check pass rate**: in TS/Python with mypy, the % of files clean of `any`/`Any` over time.

## Dependency signals

- **Stale-dep ratio**: % of direct deps more than 1 minor version behind.
- **Known-CVE count**: scanner output, severity-weighted.
- **Abandoned-dep count**: direct deps with no commit in 12+ months.
- **Lockfile churn**: how often the lockfile changes. Constant churn means dep instability.

## DX signals

- **Time to first PR for new contributor**: tracks onboarding friction.
- **Local setup time**: clean clone to running app. Above 30 minutes is friction.
- **Reproduction rate of bugs**: how often a reported bug can be reproduced from the repro steps. Below 80% means observability or repro tooling needs work.

## Architecture signals

- **Cyclic dependencies**: any cycle is a smell; large cycles are technical debt.
- **Cross-package imports**: imports that cross intended boundaries. Track count and trend.
- **Shared module count**: utilities used by 5+ packages. Often the source of unintended coupling.

## Reading the signals together

- High churn + high bug rate in same files = boundary problem
- High flake rate + slow tests = test infrastructure debt (not code debt)
- High dep churn + low test coverage = upgrade risk
- Long cycle time + low revert rate = process friction (review backlog), not quality issue
- Long cycle time + high revert rate = quality problem masquerading as throughput

## Anti-patterns when measuring

- Tracking signals that nobody acts on
- Optimizing one signal in isolation (improve test runtime by deleting tests)
- Treating signals as targets (Goodhart's Law)
- Ignoring the qualitative signal: "what hurt this week"
