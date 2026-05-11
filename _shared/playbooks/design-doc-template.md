# Design Doc Template

A design doc is for proposals where the implementation isn't obvious and the team should agree on direction before code is written.

## Shape

```
# Design: <title>

Author: <name>
Status: Draft | Reviewing | Approved | Rejected | Implemented
Date: YYYY-MM-DD
Reviewers: <names>

## Summary

One paragraph. What is the problem; what is the proposed solution. If a reader stops here, they should know whether to read more.

## Goals + non-goals

What this design achieves. What it explicitly does not address (so reviewers don't critique it for missing things out of scope).

## Background

What context does the reader need? Existing system shape, prior decisions (link ADRs), external constraints. Be concise; link rather than restate.

## Proposal

The design itself. Diagrams help. Be specific:

- Component / module shape
- Data flow
- Public surface (APIs, CLIs, configs)
- State management
- Error handling
- Observability

## Alternatives considered

For each: option, trade-offs, reason for rejection. Reviewers will ask "why not X" — answer in writing.

## Risks + open questions

What could go wrong? What is uncertain? What needs validation?

## Rollout plan

How will this ship? Phases? Feature-flagged? Migration steps?

## Validation plan

How will we know it works? Tests, metrics, manual verification, success criteria.

## References

Issues, prior docs, external links, prototypes.
```

## Quality bar

- The Summary is a single paragraph. If it's 5 paragraphs, it's not a summary.
- Goals + non-goals exist. The non-goals section prevents scope creep in review.
- Alternatives have specific reasons for rejection ("doesn't scale" is not a reason; "exceeds 5x throughput on path X under sustained load" is)
- Rollout has phases when the change is non-trivial
- Validation criteria are concrete enough to falsify

## When to write one

- The implementation isn't obvious and reasonable engineers might do it differently
- The change spans multiple services or teams
- The change has rollback/migration risk
- Decision deserves to be findable later

## When not to

- Implementation details inside a single module
- Decisions where the team has consensus and the doc would just be ceremony
- Exploratory work; write it after the prototype if the direction holds
