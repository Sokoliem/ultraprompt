# Contract Test Patterns

Contract tests pin a boundary from the consumer's perspective. They differ from unit tests (producer's internal logic) and integration tests (live integration). A contract test should fail when the producer breaks the surface in a way that affects consumers — even if producer-side tests still pass.

## What to capture

For each consumer-producer relationship:

- **Request shape**: method, path, headers required, query params, body schema
- **Response shape**: status codes, headers, body schema
- **Behavioral expectations**: ordering of items, default values, error formats, retryability semantics
- **Edge cases the consumer relies on**: empty results, max-page behavior, rate-limit response, auth-failure response

## What NOT to capture

- Internal implementation details (the producer's storage layout, internal IDs)
- Performance characteristics (those go in SLOs / benchmarks)
- Behaviors no consumer actually uses (don't pin what isn't depended on)

## Frameworks

- **Pact** — JS/Python/Java/Ruby/.NET; broker-based pact sharing; widely used
- **Spring Cloud Contract** — Java/Kotlin; producer-side contract definition with stub generation
- **Postman/Newman** — lightweight JSON-based; limited verification rigor
- **Custom JSON Schema + integration tests** — works for simpler boundaries; less ceremony

## Producer-side responsibilities

1. Run consumer-supplied contract tests in producer CI
2. On failure, the producer either fixes (matches consumer expectation) or escalates (contract change required)
3. Never mutate consumer-supplied contracts to make them pass

## Consumer-side responsibilities

1. Capture real expectations, not aspirational ones
2. Update contracts when consumer needs change; do not pin defunct expectations
3. Run contract tests against producer stubs in consumer CI

## Anti-patterns

- Contract test that's actually an integration test (calls live producer; not a contract pin)
- Schema-only contract that misses behavioral expectations
- Contract owned by producer (producer can move the goalpost when convenient)
- One contract for many consumers when consumers have different expectations
- Pinning the kitchen sink (every field, every status, every header). Pin what consumers actually depend on.

## Versioning

Contracts evolve. Strategies:

- Producer publishes versioned contracts; consumers pin the version they're built against
- Backward-compatible additions are unversioned (consumers tolerate new fields)
- Breaking changes get a new contract version + migration window
