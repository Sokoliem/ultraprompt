# ADR Template

Architecture Decision Records capture the why behind a non-obvious technical decision so future contributors can understand the reasoning without re-deriving it.

## Shape

```
# ADR-NNN: <Decision title>

Status: Proposed | Accepted | Deprecated | Superseded by ADR-MMM
Date: YYYY-MM-DD
Deciders: <names or roles>

## Context

What problem motivates this decision? What constraints apply? What are the relevant non-technical factors (team size, deadlines, external commitments)?

## Decision

What did we decide? State it directly. One paragraph.

## Alternatives considered

For each: what was the option, why was it not chosen. Be specific. "Performance" is not a reason; "5x throughput on the order-processing path measured under sustained load" is.

## Consequences

What becomes easier? What becomes harder? What new risks does this introduce? What must be revisited and when?

## References

Issues, PRs, prior ADRs, design docs, external links.
```

## Quality bar

- The decision is one paragraph, not a treatise.
- Alternatives are real (someone considered them), with specific reasons for rejection.
- Consequences include the costs, not just the benefits.
- The status field is maintained over time. Superseded ADRs are linked, not deleted.

## When to write one

- Choosing between two viable architectural patterns
- Adopting or rejecting a new dependency that affects the whole codebase
- Changing a public API in a non-trivial way
- Reversing a previous architectural decision

## When not to

- Internal implementation choices (variable names, file organization)
- Decisions made by external constraints (team has standardized on X)
- Decisions that are obvious in retrospect and don't need future justification
