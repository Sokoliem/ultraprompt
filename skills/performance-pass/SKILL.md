---
name: "performance-pass"
description: "When user says 'performance audit / find slow code / hot path review / perf optimization / performance issues / latency review / throughput audit' — dispatches reviewer with performance focus. DEFAULT for performance audits. Different from /debug (active perf bug)."
when_to_use: "Manual-only. Invoke for performance investigation or benchmark design. Do not use for general code review (use review). Do not use for CI build speed (see `_shared/playbooks/build-test-optimizer.md`)."
argument-hint: "[hot path|operation|target metric]"
tier: "specialist"
aliases: ["performance-pass"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Performance Pass

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Dispatch policy (V8)

**Dispatch target:** `ultraprompt:reviewer` (focus: `performance`). See `${CLAUDE_PLUGIN_ROOT}/_shared/DISPATCH-POLICY.md` for the full V8 dispatch decision tree, Task call template, and inline-override conditions.

## Panel escalation (V8)

Deep-budget or high-consequence versions of this lane can escalate to: `release-gate-panel`. Preferred: `release-gate-panel`. Use panel escalation for independent specialist breadth; keep the default path lighter for ordinary requests.

## Distinctive judgment

Optimize what matters, measured. Profile before optimizing; profile after to confirm. Performance work is dominated by: I/O (network, disk, DB), allocation pressure (GC), repeated work (caching opportunities), and concurrency (lock contention, false sharing). Algorithmic improvements only matter if the hot path actually executes the algorithm.

## First signals to inspect

- Profile output (CPU profile, allocation profile, flamegraph)
- Slow query logs / APM traces / span timing
- Hot path call frequency (sampling counters, request rate × per-request cost)
- Memory allocation patterns (GC frequency, allocation rate)
- Cache hit rate (where caches exist)
- Lock contention metrics where applicable

## Failure modes specific to this lane

- Optimizing without profiling (you'll optimize the wrong thing)
- Optimizing the algorithm when the hot path is I/O bound
- Adding a cache that doesn't bound size (leaks memory)
- Adding parallelism without measuring lock contention
- Micro-benchmarks that don't reflect production conditions
- Premature optimization in cold paths

## Workflow

1. Confirm there's a performance problem with concrete evidence (slow query, slow request, high CPU/memory).
2. Profile to identify the actual hot path. Don't trust intuition.
3. Classify the bottleneck: I/O, CPU, allocation, contention.
4. Apply the appropriate optimization. Measure before and after.
5. Add a benchmark that exercises the hot path realistically and would catch regression.
6. Validate: production-like load, not just unit microbenchmark.

## Validation

Benchmark before/after on representative workload. Confirm no regression in adjacent code. Profile after to confirm the hot path moved.

## Output contract

Performance Goal | Profile Evidence (where the time/allocation actually goes) | Bottleneck Classification | Optimization Applied | Before/After Numbers | Benchmark Added | Remaining Bottlenecks

## Subagent delegation

Dispatch `reviewer` with focus=performance for second-perspective profile interpretation.

## V4 aliases

This skill answers to V4 names: `performance-pass`. The router resolves them to `performance-pass` and notes the alias in its response.
