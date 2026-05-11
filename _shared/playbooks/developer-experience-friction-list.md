# Developer Experience Friction List

DX friction is debt with compounding interest: every contributor pays the cost on every cycle. The signals are concrete and observable.

## Onboarding friction

- [ ] Time from clean clone to a passing test on a new contributor's machine
- [ ] Number of out-of-band install steps not in the README (homebrew packages, environment variables, secrets)
- [ ] Number of OS-specific failures (Windows, macOS Apple Silicon, Linux) not handled by setup scripts
- [ ] Documentation drift: README install commands that don't actually work

## Inner-loop friction

- [ ] Time from save-file to test-result locally (target: <10s for unit tests)
- [ ] Time from save-file to seeing the change in the dev server (hot-reload SLA)
- [ ] Type-check feedback: language server lag, false positives that train developers to ignore signal
- [ ] Manual restart required for changes that should hot-reload
- [ ] Build cache hit rate; cold builds dominating wall-clock time

## CI friction

- [ ] Total CI duration from PR push to feedback (target: <10 min for the critical path)
- [ ] Flake rate (target: <1%; above 1% trains developers to retry-without-thinking)
- [ ] Required-checks shape: ordered to fail-fast on cheap signals (lint < unit < integration < e2e)
- [ ] Cache hit rate; persistent miss is wasted minutes per run

## Toolchain friction

- [ ] Errors from tools where the message doesn't tell you how to fix it ("Type error in node_modules/x.d.ts")
- [ ] Tools that require manual config-file maintenance for things they could auto-detect
- [ ] Conflicting opinions between tools (formatter formats, linter unformats)
- [ ] Versions pinned in some places, drifted in others (`.nvmrc`, `engines`, CI workflow each saying different)

## Code-finding friction

- [ ] Search returns 100+ results because a common name is reused across packages
- [ ] Generated code mixed with handwritten code, no convention for distinguishing
- [ ] No way to find tests for a given source file (or vice versa) without grep gymnastics
- [ ] Implicit conventions ("magic strings used as enum values") not searchable

## Review friction

- [ ] PR template missing or under-used (every PR needs the same questions answered)
- [ ] Review-required reviewer count higher than necessary (review backlog grows)
- [ ] Required checks block reviews even for docs-only changes
- [ ] No way to see what changed since previous review on the same PR

## Where to start

Pick the friction with the highest contributor-hour impact. Track it before and after fixing. Trim the dead weight (deprecated tools, unused configs) before adding new tooling.

## Anti-patterns

- Adding tooling on top of existing tooling instead of consolidating
- "Documentation will fix it" — usually it's a tool problem, not a doc problem
- Optimizing for the experienced contributor (they don't notice friction; new contributors do)
