# Cron Job Audit Checklist

Scheduled jobs accumulate over years and silently break. Most teams discover this only when something user-facing depends on a cron that hasn't run successfully in months.

## Inventory

For each repo / service / cluster:

- List every scheduled job: cron files, Kubernetes CronJob, Cloud Scheduler, GitHub Actions schedule, Heroku Scheduler, AWS EventBridge rules
- Schedule expression and timezone (UTC vs local; daylight-savings interactions)
- Job command / entrypoint
- Owner (team or individual)
- Last successful run timestamp
- Last failure timestamp + reason

## For each job, verify

- [ ] **Alerting on failure**: a failed run pages someone, or surfaces in a dashboard someone watches
- [ ] **Alerting on missed run**: if the job didn't fire at all (scheduler misconfiguration), is anything noticing?
- [ ] **Idempotent or transactional**: can it run twice without corrupting state? (Critical because schedulers retry under failure.)
- [ ] **Bounded duration**: does it have a timeout? What happens if it runs longer than the schedule interval?
- [ ] **Resource limits**: memory/CPU/network limits set; long-running jobs without limits can starve the cluster
- [ ] **Dependencies still exist**: does the job call services or APIs that have been retired?
- [ ] **Output observable**: logs go somewhere queryable; metrics emitted on success/failure/duration
- [ ] **Backfill story**: if a run is missed, is the job designed to catch up, or does that require manual intervention?

## Common failure modes

- **Silent failure**: job succeeds-from-scheduler-perspective but the work didn't happen (caught exception, fallthrough)
- **Quota exhaustion**: monthly job hits an annual quota and stops running unnoticed
- **Credential expiry**: job uses a service-account credential that rotated; failures look like auth errors but no one looks
- **Schedule drift**: codebase moved time zones, daylight-savings flipped the schedule, or cron expression silently failed validation
- **Compounding delay**: job takes longer over time as data grows; eventually overlaps with the next run

## Patterns for resilient cron jobs

- Emit a heartbeat metric at the start and end; alert if either is missing for N intervals
- Use a job runner with idempotency tokens (e.g., a job ID that prevents double-execution)
- For long jobs, design for resumability (checkpoint progress; on restart, continue)
- Log exit code + duration always; treat success-with-no-progress as a failure if it should have done something

## When to retire a job

- It hasn't produced a useful artifact in 3+ months
- The downstream consumer has been replaced
- The job's output is unobserved (no dashboard, no alert, no consumer)

Retire by deleting, not by extending the schedule to "every 365 days" or commenting out and forgetting.
