# Monorepo Architecture Checklist

Monorepos amplify both good and bad architectural decisions. The questions below are about whether the structure scales.

## Package structure

- [ ] **Public surfaces are explicit**: each package declares its `exports` / public API; internal modules aren't importable from outside
- [ ] **Dependency direction is acyclic**: a package graph traversal terminates; no `apps/web → packages/foo → apps/web` cycles
- [ ] **Layering is intentional**: foundation packages (logging, types) → domain packages → app packages; no jumping layers
- [ ] **One package, one responsibility**: a package called `utils` is a smell — what's actually in it?
- [ ] **Naming maps to ownership**: package names suggest who owns them (team prefix, domain prefix)

## Build system

- [ ] **Affected-package build**: a change to one package only rebuilds + retests downstream-affected packages
- [ ] **Build cache shared across CI runs**: Nx, Turbo, Bazel, or comparable; cold rebuild is the exception
- [ ] **Cross-package types resolve in editor**: contributors get IntelliSense across package boundaries
- [ ] **Single command for everything**: `pnpm build`, `pnpm test`, `pnpm lint` work from root and from any package
- [ ] **Versioning strategy**: independent versions (changesets) or fixed (lerna fixed) — chosen, not accidental

## Test isolation

- [ ] **Tests run in package scope**: a test in package A can't affect package B's state
- [ ] **No global setup leaking across packages**: shared fixtures explicit, not magic
- [ ] **Cross-package integration tests are separate**: not bundled into every package's unit tests

## Tool configuration

- [ ] **Linter / formatter / typecheck config inherited from root**: package-level overrides only when needed
- [ ] **Editor experience is consistent**: same VSCode settings work for any package
- [ ] **Tooling versions pinned at root**: not drifted across packages

## Boundary enforcement

- [ ] **Lint rule prevents cross-boundary imports**: `eslint-plugin-import` boundaries, `dependency-cruiser`, `madge`
- [ ] **CODEOWNERS reflects package ownership**: review enforcement at boundary
- [ ] **Public API changes require explicit review**: breaking changes don't slip through

## Smells

- **God package**: one package depended on by everything else. Often called `core`, `common`, `shared`. Often becomes a dumping ground.
- **Cyclic deps**: package A imports B, B imports A (sometimes via a third package). Build will work; logical structure won't.
- **Implicit shared state**: packages that "happen to work" because they read/write the same global. Breaks when one package is reused independently.
- **Test depending on app**: a test in package A imports app code from package B that should be encapsulated. Fragile.
- **App package importing internal modules**: bypasses public surface; breaks when internals refactor.

## When to split a package

- Multiple consumers depend on a subset that has its own coherent surface
- Build / test time of the package is dominating the inner loop
- Two teams are constantly stepping on each other in the same package

## When NOT to split

- "It feels too big" — ergonomic feeling, not measured friction
- Anticipating future use cases that haven't materialized
- Premature abstraction; one consumer is rarely enough to design a public API

## Migration from non-monorepo

If migrating into a monorepo from separate repos:

- Keep history (`git filter-repo`, `tomono`); don't lose blame
- Adopt the build system before adopting the structure
- Move the highest-coupling repos first; standalone repos can stay separate longer
