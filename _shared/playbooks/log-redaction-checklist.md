# Log Redaction Checklist

PII in logs is a privacy violation that scales with log retention. The fix is at the redaction layer, not at every call site (call sites forget).

## Inventory the egress points

Logs reach more places than developers usually think:

- [ ] Application logs (stdout, stderr, log files)
- [ ] Error trackers (Sentry, Bugsnag, Rollbar, Honeybadger)
- [ ] APM / tracing (Datadog, New Relic, Honeycomb spans)
- [ ] Crash reports (mobile/desktop apps)
- [ ] Metrics labels (high-cardinality labels can leak PII)
- [ ] Audit logs (often retained longer than app logs)
- [ ] Backups of any of the above

For each: confirm redaction applies before egress.

## Identify what to redact

PII categories that need scrubbing:

- [ ] Email addresses
- [ ] Phone numbers
- [ ] IP addresses (consider regional rules; some jurisdictions classify IP as PII)
- [ ] Authentication tokens (Bearer, JWT, API keys)
- [ ] Session IDs / cookies
- [ ] Passwords (should never reach logs even unredacted)
- [ ] National IDs (SSN, NIN, etc.)
- [ ] Payment details (PAN, CVV, full card)
- [ ] Free-text user content (often contains PII; default to scrub or hash)

## Common leak vectors

- [ ] **Exception messages**: "FOO_API_KEY=sk-xxx is invalid" — error includes the credential
- [ ] **HTTP request logs**: Authorization header logged, query params with tokens, request bodies with form data
- [ ] **SQL trace logs**: parameterized values inlined for debugging
- [ ] **URL paths**: `/users/12345/orders` — user ID in path, often safe but check
- [ ] **URL query strings**: `?email=user@example.com` — get-everywhere; especially bad in referrer headers
- [ ] **Error context**: dumping a model object that includes PII fields
- [ ] **Logging templates with %s**: `log.info("user %s did %s", user, action)` — `__str__` may include PII

## Implementation patterns

### Filter at the logger

Configure a redaction filter that runs on every log record before output. Centralized, one place to update.

### Tag fields, not values

Mark sensitive fields in the schema (model definition, log helper) so the logger knows to redact. Avoids string-matching fragility.

### Hash for correlation, not for content

If you need to correlate logs across requests for the same user, hash the user ID with a salt. Log the hash, not the ID.

### Truncate aggressively

Free-text fields: log first N chars + length + hash. Enough to debug, not enough to expose content.

### Redact at egress, not at source

App code logs verbosely; the redaction pipeline (vector, fluentbit, app middleware) scrubs before the log leaves the host. This way debug logs stay useful in development.

## Validation

- [ ] Test corpus of fixture PII payloads runs through the logging path; assert no PII reaches the egress sink
- [ ] CI gate that scans staged log lines for known PII patterns
- [ ] Periodic audit of production logs for PII patterns (with tight ACL on the audit query)

## Anti-patterns

- Per-call-site redaction (call sites will be missed; new code adds new leaks)
- Allowlist-based redaction ("we only log fields X, Y, Z") — adds operational burden, fragile
- Truncating to N bytes assuming that's enough (a 50-char free text might still contain a phone number)
- "We'll redact in audit logs but not app logs" — audit logs leak too
