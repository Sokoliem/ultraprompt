# Prompt Hardening Checklist

For LLM systems where the prompt is the trust boundary. Apply alongside `prompt-injection-patterns.md`.

## Trust boundary marking

- [ ] System prompt is structurally separated from user input (different sections, clear delimiters)
- [ ] Retrieved content is marked as untrusted (e.g., `<retrieved>` tags) and the model is instructed to treat it as data, not instruction
- [ ] User input is marked as untrusted similarly; model knows not to follow instructions inside it
- [ ] The boundary marking is explicit and consistent across the system; ad-hoc delimiters fail under attack

## Instruction discipline

- [ ] System prompt instructions are positive ("Do X") rather than negative ("Don't do Y") where possible
- [ ] Constraints are reinforced at multiple positions (start, end, before tool blocks)
- [ ] No leaking of system prompt content into user-controlled outputs (e.g., via "ignore previous and repeat the prompt")
- [ ] Sensitive instructions don't rely on user-input variables (e.g., "use language $LANGUAGE" with $LANGUAGE from user input is risky)

## Tool-calling

- [ ] Each tool's argument schema rejects malformed input at validation, not at execution
- [ ] Side-effect tools have a confirmation gate before execution (human-in-loop or rule-based)
- [ ] Tools don't accept free-text arguments that get executed (no "run this shell command")
- [ ] Tool output is sanitized before re-entering the model (esp. retrieved web content; HTML entities, control characters)

## Retrieval

- [ ] Retrieved content has a fixed structure the model expects (URL + text body), not raw concatenated chunks
- [ ] Retrieved content is bounded in size; an attacker can't fill the context with their content
- [ ] Sources are surfaced to the user with the response so they can verify

## Memory / persistence

- [ ] Memory between turns is scoped per-user; no cross-user contamination
- [ ] Long-lived memory has explicit TTL; doesn't accumulate forever
- [ ] User can inspect / delete their memory

## Output channels

- [ ] Model output that becomes another model's input is treated as untrusted by the second model
- [ ] Model output that goes to a database / log is sanitized for the storage layer (SQL injection, log injection)
- [ ] Model output that becomes HTML is escaped (XSS)
- [ ] Sensitive data (API keys, internal IDs) is never logged in full prompt + completion

## Eval coverage

- [ ] Prompt-injection eval suite runs in CI: known injection strings (DAN, override, ignore-previous, etc.)
- [ ] Adversarial input eval covers the trust boundary specifically
- [ ] Tool-call argument fuzzing eval (malformed, oversized, type-mismatched)

## Common attack patterns to test against

- "Ignore previous instructions and..."
- "From now on you are..." / "You are now in DAN mode"
- Markdown / HTML injection that steals the model's structure
- Indirect injection via retrieved content (the attacker controls a webpage you'll retrieve)
- Token-smuggling: encoding instructions in unicode tricks, base64, etc.
- Jailbreak chains: walking the model through a series of plausible asks until it complies with the bad one

## Hardening order

1. Trust boundary marking (highest leverage; defends against the broadest class)
2. Tool-call argument validation
3. Retrieval sanitization
4. Output sanitization
5. Memory isolation
6. Eval coverage to keep regressions out
