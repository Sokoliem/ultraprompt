# Incident Postmortem Template

Postmortems exist to make the next incident less likely. Blame-free in tone; specific in fact.

## Shape

```
# Incident Postmortem: <short title>

Date: YYYY-MM-DD
Severity: SEV-1 | SEV-2 | SEV-3
Duration: HH:MM (start → resolution)
Author: <name>
Status: Draft | Reviewed | Closed

## Summary

One paragraph. What happened, who was affected, when it was resolved.

## Impact

- Users affected: <count or %>
- Functionality impaired: <specific features>
- Duration of degradation: <minutes>
- Revenue / SLA impact: <if measurable>
- Data loss / corruption: <yes/no, scope>

## Timeline

In UTC. Lead with detection, end with resolution. Each entry: timestamp + what happened + who acted.

- HH:MM — <event>
- HH:MM — <event>
- ...

## Root cause

What actually caused the incident? Be specific. Not "deployment caused issue" but "the deployment introduced a regex that ReDoS'd on inputs containing >1024 consecutive whitespace chars; the fuzzer didn't cover this."

If multiple contributing factors, list them all. Real incidents usually have multiple.

## What went well

What detected the incident? What allowed responders to mitigate quickly? Acknowledge the systems that worked.

## What went poorly

What slowed detection or response? What confused responders? Where did process or tooling fail?

## Action items

For each: specific, owned, dated. Track elsewhere (issue tracker, ticket).

- [ ] <action> — owner: <name> — by: <date>
- [ ] <action> — owner: <name> — by: <date>

## Lessons

What's the takeaway for the broader team? One or two sentences.
```

## Quality bar

- Blame-free language: "the deploy introduced..." not "Alice introduced..."
- Specific facts: timestamps, numbers, file/line references, error messages
- Action items are concrete and owned, not aspirational
- Lessons section is honest: real lessons, not platitudes ("we'll be more careful")

## Anti-patterns

- "We'll add more tests" — always true, never specific enough to act on
- Hidden root cause: writing around it because it's politically uncomfortable
- Action items without owners or dates (won't get done)
- Skipping "what went well" — this section reinforces the systems that worked

## Process

- Postmortem within 5 working days of resolution
- Reviewed by at least one engineer not directly involved in the incident
- Action items tracked separately and revisited weekly until closed
- Document is searchable and findable; future incidents reference past ones
