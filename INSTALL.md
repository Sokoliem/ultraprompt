# Ultraprompt V8 Install

## Quick Install

### Windows / PowerShell

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 both
```

The Windows installer uses `py -3`, installs into the active `ultraprompt-local` Claude Code and Codex marketplaces, applies Windows MCP and hook command variants, backs up the previous install, rebuilds generated V8 indexes, and refreshes Codex's plugin cache.

### macOS / Linux

```bash
bash scripts/install.sh both
```

This backs up the previous install, copies V8 to each runtime-specific plugin path, applies the correct MCP manifest, updates marketplace catalogs, and runs schema audit plus plugin validation.

## Per Runtime

### Claude Code

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 claude-code
```

```bash
bash scripts/install-claude-code.sh
```

Installs to `~/.claude/plugins/marketplaces/local-marketplace/ultraprompt/`. After install, restart Claude Code and confirm `/mcp` shows `ultraprompt-meta`.

### Codex

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\install-windows.ps1 codex
```

```bash
bash scripts/install-codex.sh
```

Installs to `~/.codex/local-marketplace/plugins/ultraprompt/`, mirrors Claude and Codex manifests, and refreshes the Codex plugin cache. After install, fully quit and relaunch Codex, then confirm `/mcp` shows `ultraprompt-meta`.

## Verify

```bash
python3 ~/.claude/plugins/marketplaces/local-marketplace/ultraprompt/scripts/validate-plugin.py
python3 ~/.claude/plugins/marketplaces/local-marketplace/ultraprompt/scripts/release-scorecard.py
python3 ~/.claude/plugins/marketplaces/local-marketplace/ultraprompt/mcp/ultraprompt_meta.py --self-test
```

Expected V8 shape: 48 skills, 29 agents, 42 MCP tools, 30 commands, 12 panels, and 17 artifact schemas.

## Dashboard

```bash
python3 ~/.claude/plugins/marketplaces/local-marketplace/ultraprompt/scripts/dashboard.py
```

The dashboard streams Claude Code and Codex ledger events plus V8 cognitive events into the live activity pane.

## Optional Monitor

For between-session safety on macOS:

```bash
/ultraprompt:install-monitor
```

Configure watched repos in `~/.claude/ultraprompt.toml`:

```toml
[watched_repos]
paths = ["~/development"]
```

## Rollback

Installers create timestamped backups:

- Claude Code: `~/.claude/backups/ultraprompt-pre-v8-<timestamp>/`
- Codex: `~/.codex/local-marketplace/backups/ultraprompt-pre-v8-<timestamp>/`

If the monitor is installed, remove it with `/ultraprompt:uninstall-monitor` before restoring an older install.
