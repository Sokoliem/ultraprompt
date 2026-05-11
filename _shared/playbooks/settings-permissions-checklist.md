# Settings + Permissions Checklist

For Claude Code plugin and agent settings: least-privilege defaults; explicit when permissions widen.

## Plugin manifest

- [ ] `name` lowercase, hyphenated, matches the directory name
- [ ] `version` follows semver and matches CHANGELOG
- [ ] `description` describes capabilities, not marketing
- [ ] No model/effort/context pins (runtime neutrality)

## Skills

- [ ] `allowed-tools` is the minimum needed; default to read-only when the skill doesn't edit
- [ ] `disable-model-invocation: true` for specialist/ecosystem skills (manual-only)
- [ ] `argument-hint` is concise and matches the actual input the skill expects
- [ ] No raw paths to user-controlled directories baked into the body

## Agents

- [ ] `tools` is the minimum needed; `Read, Grep, Glob` as default; `Bash` only for read-only discovery
- [ ] `disallowedTools` explicitly excludes `Write, Edit, MultiEdit` for read-only agents
- [ ] `maxTurns` is set; runaway agents are a primary failure mode
- [ ] No model pin

## Hooks

- [ ] Each hook recipe has a precise `matcher` (specific tool list, not `*`)
- [ ] Each hook fails-open on parse errors
- [ ] Each hook respects `ULTRAPROMPT_DISABLE_HOOKS=1`
- [ ] Sensitive hooks (e.g., Stop validation) are opt-in via env var
- [ ] Each hook has fixture tests
- [ ] Each hook has a `timeout` (5-10 seconds is typical)
- [ ] Hook side effects (evidence ledger writes) don't block the main flow

## Commands

- [ ] `description` accurate and brief
- [ ] `disable-model-invocation: true` for utility commands not intended as skill substitutes
- [ ] `allowed-tools` matches what the command body invokes; not broader

## MCP servers

- [ ] `.mcp.json` declares command, args, optional env
- [ ] Server self-tests with `--self-test` flag
- [ ] Tools default to read-only; write tools named clearly
- [ ] No tool runs arbitrary code from user input

## Output styles

- [ ] `name`, `description`, optional `keep-coding-instructions`
- [ ] No instructions that conflict with the model's safety policies
- [ ] Body content is style guidance, not capability changes

## Marketplace metadata

- [ ] Description matches reality (not aspirational)
- [ ] Keywords are relevant (not seo-stuffing)
- [ ] License declared

## Defaults

- [ ] Plugin works on a fresh install with zero env-var configuration
- [ ] Telemetry is opt-in (off by default)
- [ ] Stop validation gate is opt-in (off by default)
- [ ] Hook disable env var is documented

## Smells

- Hook matchers using `*` (intercepts everything; high collateral cost)
- Agent with `Write` permission that doesn't write
- Skill that recommends destructive actions without confirmation
- MCP tool with side effects but a name like `get_*` or `list_*`
- Plugin manifest with model/effort pins (locks runtime profile against user choice)
