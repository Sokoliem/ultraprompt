# Agent Team Orchestration Patterns

When dispatching multiple subagents, the orchestration pattern matters as much as the agents themselves. The wrong pattern wastes context and produces conflicting findings without resolving them.

## Patterns

### Fanout

Same problem, multiple lenses. Use when independent perspectives reduce risk.

- Examples: review-fanout (security + perf + arch + tests), migration-assess (api + db + infra)
- Synthesis: agreement = high-confidence finding, conflict = surface for human, gap = no panelist covered (often a hole)
- Cost: N × baseline; only worth it on consequential work

### Triangulation

Same symptom, competing hypotheses. Use when root cause is unclear and multiple plausible explanations exist.

- Example: debug-triangulate (3+ debuggers each starting from a different hypothesis)
- Synthesis: which hypothesis matched the evidence; the others can be rejected with concrete reasoning
- Cost: N × baseline, but races them in parallel

### Pipeline

Sequential handoff. Use when later steps depend on earlier ones.

- Example: scout maps the repo → reviewer reviews specific files → writer drafts the changelog
- Synthesis: each step's output is the next step's input; failures stop the pipeline
- Cost: roughly additive; harder to parallelize

### Hub-and-spoke

Main thread coordinates; specialists are dispatched as needed.

- Example: main thread owns the diff; dispatches `auditor focus=db` only if migration files appear in the diff
- Synthesis: main thread integrates each specialist's findings into the user-facing answer
- Cost: only what the situation requires

## When to NOT spawn agents

- Simple, local work where direct inspection is faster
- Token cost would dominate the value
- The task's bottleneck is decision-making, not parallelizable work

## Dispatch hygiene

- Pass the task description with explicit `focus:` parameter when using parameterized agents
- Pass the relevant context concisely; do not paste large diffs that the agent can re-read
- Specify the return contract: "return findings as a severity-ordered list with confidence tags"
- Set `max_turns` appropriately; runaway agents are a primary failure mode

## Synthesis discipline

- Surface agreement (multi-agent confirmation = high confidence)
- Surface conflict explicitly (do not pick a side silently)
- Surface gaps (what nobody covered may be the real risk)
- Resist the urge to paste each agent's full report — synthesize, do not concatenate
