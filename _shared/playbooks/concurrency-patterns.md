# Concurrency Patterns

Concurrency bugs are the hardest to reproduce and the hardest to debug. The patterns below are about prevention; once a race is in production, your options narrow significantly.

## The variables

Most concurrency bugs come from one of these:

- **Time**: race between operations that overlap in time
- **Order**: dependence on an order that the runtime does not guarantee
- **Shared state**: two paths writing to the same memory / row / file / cache
- **Atomicity**: a sequence that should be all-or-nothing isn't
- **Visibility**: writes that aren't visible to readers across threads/cores/replicas

## Patterns by language family

### Async (JS, Python asyncio)

- `await` does not lock; concurrent awaits can interleave on shared state
- `Promise.all`/`asyncio.gather` runs all branches concurrently — if they share state, they can race
- Don't `await` inside a critical section that you want atomic; serialize via a lock primitive

### Threaded (Java, Go, Rust, C#)

- Locks must be ordered; out-of-order acquisition causes deadlock
- Read-modify-write on shared variables needs atomic ops or a lock
- Mutexes around large critical sections kill throughput; reduce scope
- Channels (Go, Rust) are safer than shared memory for cross-goroutine communication

### Distributed (multiple processes / replicas)

- "It worked on one node" doesn't mean it works on N nodes
- Database transactions don't span service boundaries
- Optimistic locking (CAS, version columns) is usually preferred over pessimistic for read-heavy workloads
- Distributed locks are not free; they have correctness gotchas (clock drift, lease expiration)

## Common bugs

### Check-then-act

```
if not exists(key):
    create(key)
```

Two threads can both see "doesn't exist" and both create. Use atomic operations: INSERT ... ON CONFLICT, or a unique constraint, or a lock.

### Lost update

```
x = read(key)
write(key, x + 1)
```

Same problem. Use atomic increment, or compare-and-swap, or a transaction.

### Iterator invalidation

Mutating a collection while iterating over it. Use a copy or an iterator that supports concurrent modification.

### Timer drift

`setTimeout(handler, 1000)` does not guarantee 1000ms. For ordering, do not rely on timers; use sequencing primitives.

### Cache stampede

Cache miss → N concurrent requests recompute the value → all write to cache. Use a lock around the recompute, or single-flight pattern, or stale-while-revalidate.

### Replication lag

Write to primary, read from replica may not see the write. Either route reads to primary for read-after-write paths, or use causal-consistency tokens.

## Detection

- Run the test under load (parallelism × volume) — many races only show up under contention
- Run with race detectors (`go test -race`, ThreadSanitizer, Helgrind)
- Property-based or fuzz-testing for state-machine code
- Production: trace correlation IDs across replicas; look for impossible interleavings

## Anti-patterns

- Adding a sleep "to fix the race"
- Catching the resulting exception ("CASException: try again") without addressing the cause
- Disabling parallelism in tests instead of fixing the race
- Single-threading everything to avoid the problem (kills throughput)
