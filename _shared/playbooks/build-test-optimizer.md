# Build + Test Optimizer Patterns

Build and test speed is debt with compounding interest. Every contributor pays the cost on every cycle.

## Profile first

Do not optimize without measurement. Most build/test pipelines have a long tail (one or two stages dominate) but contributors guess wrong about which.

- For CI: most providers expose per-step timing
- For local: time the wall clock of each major phase (deps install, compile, test, lint)
- Identify the dominant 1–3 cost centers; ignore the rest until those are fixed

## Common cost centers

### Dependency install

- Cache `node_modules`/`vendor`/Cargo cache by lockfile hash
- Use the strict-lockfile command (`npm ci`, `pnpm install --frozen-lockfile`, `pip install --require-hashes`)
- Avoid `npm install` in CI — it can drift the lockfile

### Compile / typecheck

- Incremental: cache build outputs by source hash
- Parallelize when the build system supports it (`make -jN`, parallel cargo)
- For TypeScript: `tsc --build` with project references; isolated builds per package

### Test execution

- Parallelize at the test runner level (jest --maxWorkers, pytest -n, cargo test --jobs)
- Shard across CI runners for large suites; ensure shards are roughly balanced
- Run fast tests first; fail fast on quick signals before paying for slow ones
- Identify and fix flakes; a flake retried 3× is paying 3× cost

### Lint / format

- Run only on changed files in pre-commit; full sweep in CI
- Parallel where supported (eslint, ruff, clippy)
- Cache results when the linter supports it

### Cache shape

- Cache key includes lockfile + tool versions; stale keys waste storage and miss hits
- Restore-keys should be a fallback chain, not just one key
- Watch cache miss rate in CI logs; sustained miss rate means the key is wrong

## Anti-patterns

- Increasing timeouts to make things "pass"
- Skipping tests to make CI fast (debt later)
- Optimizing the cold path while the hot path is untouched
- Adding parallelism without measuring lock contention or I/O saturation
- Caching everything (cache invalidation bugs cost more than the wins)

## Measure after

After each change, measure again. If the change did not improve the dominant cost center, revert and try something else.
