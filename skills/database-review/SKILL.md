---
name: "database-review"
description: "When user says 'database review / DB schema review / migration review / query performance / DB design review / check this SQL / look at the schema / data model review' — dispatches reviewer with database focus (schema, migrations, query patterns, indexing, transactions). DEFAULT for database-focused reviews."
when_to_use: "Manual-only. Invoke for database-specific work: schema design, migration safety, index strategy, transaction boundaries, query plans, backfill design. For general migration sequencing, use core `migrate`."
argument-hint: "[table|migration|query|operation]"
tier: "specialist"
aliases: ["database-review"]
disable-model-invocation: true
allowed-tools: "Read, Grep, Glob, Bash, Write, Edit, MultiEdit, Agent"
---

# Database Review

Apply discipline per `${CLAUDE_PLUGIN_ROOT}/_shared/DISCIPLINE.md` (covers `$ARGUMENTS` handling, evidence, validation, and safety).

## Distinctive judgment

Database changes are rarely reversible cheaply. Schema, indexes, and data are entangled with application code, replicas, and backups. Migration safety has two dimensions: (1) the migration completes without breaking the live system, (2) the new schema works correctly under production load. Both must be verified before commit.

## First signals to inspect

- Schema migration tool and convention (Alembic, Flyway, Liquibase, Rails, Prisma migrate)
- Production data scale (rows, GB) of affected tables — migration time is a function of size
- Indexes on affected columns; query plans for affected queries
- Foreign key relationships and cascade behavior
- Replication topology: primary/replica, lag tolerance
- Transaction isolation level and locking patterns
- Backup and restore strategy

## Failure modes specific to this lane

- Adding a column with a default value to a large table (rewrites the whole table; locks for hours)
- Adding an index on a hot table without CONCURRENTLY (in Postgres) or ONLINE (in MySQL)
- Changing column type in a way that requires a rewrite
- Backfill that runs in a single transaction (locks, blows up replication lag)
- Foreign key cascade that surprises during a deletion
- Migration that breaks rolling deploys (mixed-version traffic against new schema)

## Workflow

1. Identify the change: schema, index, query, transaction boundary, or backfill.
2. Estimate impact at production scale (data volume, lock duration, replication impact).
3. For schema: forward-compatible step first (add nullable, deploy, populate, deploy, make non-null).
4. For index: use online/concurrent index creation; verify with query plan.
5. For backfill: chunked, idempotent, with progress tracking and pause/resume.
6. Test on production-scale dataset where possible.
7. Document rollback for each step (especially the irreversible ones).

## Validation

Run migration on production-scale copy. Time the operation. Verify query plans changed as expected. Test rolling deploy with mixed-version application code.

## Output contract

Change Type | Production Scale Impact | Sequenced Steps (forward-compat first) | Online Index/Lock Strategy | Backfill Plan (chunked, resumable) | Query Plan Verification | Rollback Per Step | Validation Performed

## Subagent delegation

Dispatch `auditor` with focus=db for a second perspective on production safety.

## V4 aliases

This skill answers to V4 names: `database-review`. The router resolves them to `database-review` and notes the alias in its response.
