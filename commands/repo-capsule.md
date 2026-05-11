---
description: When entering an unfamiliar repo or starting cross-cutting work, fetch a cached read-only contract: validation commands, configs, ownership, sensitive paths, recent activity. Faster than manual ls/cat tour. Cached by HEAD.
disable-model-invocation: true
argument-hint: [path] [--diff-since <ref>] [--force-refresh]
---

# Repo Capsule (V8)

Generate or fetch a repository contract capsule. Default path is the current working directory; if `$ARGUMENTS` starts with a path, use that.

Preferred path:

1. If the `ultraprompt-meta` MCP server is available, call `repo_capsule` with the path. Pass `force_refresh: true` if `--force-refresh` was given. The MCP tool serves cached results when HEAD is unchanged.
2. For drift, call `repo_capsule_diff` with the `since_commit` from `--diff-since <ref>`.
3. Otherwise, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/repo-capsule.py" --repo <path> --format markdown`.

Surface:

- Guidance files (CLAUDE.md, AGENTS.md, CONTRIBUTING.md, README, .cursorrules)
- Package managers and lockfiles
- Validation commands (test, lint, typecheck, build) inferred from package manifests, Makefile, CI workflows
- CI workflow files
- Configuration files (tsconfig, eslint, vitest, terraform, etc.)
- Migration directories
- Ownership files (CODEOWNERS)
- Sensitive path matches (.env, *.pem, *.key, secrets.*)
- Release hints

If `--diff-since` was passed, surface what changed in the contract (validation command moved, config file added, ownership shifted).

Cached at `${CLAUDE_PLUGIN_DATA}/capsules/<repo-hash>-<HEAD>.json`. Stale cache is automatically invalidated when HEAD changes.

This command is read-only. It does not modify the repository.
