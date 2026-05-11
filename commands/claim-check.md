---
description: Verify a draft answer against the evidence ledger before output. Flags claims of validation/passing/successful that lack supporting ledger events.
disable-model-invocation: true
argument-hint: <draft answer text>
---

# Claim Check (V8)

Scan `$ARGUMENTS` (your draft answer) for unbacked validation claims. The Stop hook is a backstop; this is the primary check.

Preferred path:

1. If the `ultraprompt-meta` MCP server is available, call `claim_check` with the draft text. Returns warnings if the draft asserts validation occurred (tests passed, build green, lint clean) without supporting ledger entries.
2. Otherwise, run the claim checker locally:
   - `echo "$ARGUMENTS" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evidence-ledger.py" claim-check`

Output:

- **Pass**: no unbacked claims found; the draft is consistent with the ledger
- **Warnings**: unbacked claims listed with the claim text and the missing evidence type (validation command, test run, etc.)

Recommended use:

- Call `claim_check` after drafting your final answer, before producing it
- If warnings appear, either run the missing validation or reword the claim to match what was actually done (e.g., "I did not run the test suite" instead of "all tests passed")

This is a self-verification tool. It does not block output. The Stop hook (when `ULTRAPROMPT_ENABLE_STOP_HOOK=1`) will block on the same condition at session end.
