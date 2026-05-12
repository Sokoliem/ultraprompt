#!/usr/bin/env bash
# V8 Claude Code installer: backup, copy, validate.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_ROOT="$HOME/.claude/plugins/marketplaces/local-marketplace"
TARGET="$MARKETPLACE_ROOT/ultraprompt"
BACKUP_DIR="$HOME/.claude/backups/ultraprompt-pre-v8-$(date +%Y%m%d-%H%M%S)"

echo "Ultraprompt V8 - Claude Code installer"
echo "Source: $SOURCE"
echo "Target: $TARGET"

# Backup existing install if present
if [ -d "$TARGET" ]; then
  mkdir -p "$BACKUP_DIR"
  cp -R "$TARGET" "$BACKUP_DIR/ultraprompt"
  echo "✓ Backed up existing install: $BACKUP_DIR"
fi

# Copy
mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
python3 "$SOURCE/scripts/package-plugin.py" --copy-to "$TARGET" >/dev/null

python3 - "$TARGET" "$MARKETPLACE_ROOT/.claude-plugin/marketplace.json" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
marketplace = Path(sys.argv[2])
plugin = json.loads((target / ".claude-plugin" / "plugin.json").read_text())
marketplace.parent.mkdir(parents=True, exist_ok=True)
marketplace.write_text(json.dumps({
    "name": "local-marketplace",
    "owner": {"name": "Local"},
    "plugins": [{
        "name": plugin["name"],
        "description": plugin["description"],
        "source": "./ultraprompt",
        "version": plugin["version"],
    }],
}, indent=2) + "\n")
PY

# Make scripts executable
chmod +x "$TARGET/scripts/"*.py "$TARGET/scripts/"*.sh "$TARGET/hooks/recipes/"*.py "$TARGET/hooks/recipes/"*.sh "$TARGET/mcp/"*.py 2>/dev/null || true

# Keep runtime-specific MCP variants in the installed tree. Claude Code reads
# ./.mcp.json, but validators and dual-runtime parity checks also expect the
# Codex manifest reference to remain satisfiable.

# V8: Rebuild generated indexes (Windows installer does this; Mac install also needs to)
echo
echo "=== Rebuild generated indexes ==="
python3 "$TARGET/scripts/build-skill-index.py" 2>&1 | tail -2
python3 "$TARGET/scripts/build-catalog-metadata.py" 2>&1 | tail -2
python3 "$TARGET/scripts/build-capability-graph.py" 2>&1 | tail -2

# Validate
echo
echo "=== Validation ==="
cd "$TARGET"
python3 scripts/audit-manifest-schemas.py || echo "FAIL: schema audit"
python3 scripts/validate-plugin.py 2>&1 | tail -8

echo
# V8: Write install manifest for atomic rollback (PRD §8.6)
PLUGIN_VERSION=$(python3 -c "import json; print(json.load(open('$TARGET/.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo "unknown")
python3 "$TARGET/scripts/install-manifest.py" write "$TARGET" --backup-root "$BACKUP_DIR" --plugin-version "$PLUGIN_VERSION" >/dev/null 2>&1     && echo "✓ Install manifest written"     || echo "  (manifest write skipped — non-blocking)"

if command -v claude >/dev/null 2>&1; then
  echo
  echo "=== Refresh Claude Code plugin cache ==="
  if claude plugins update ultraprompt@local-marketplace >/tmp/ultraprompt-claude-plugin-update.log 2>&1; then
    cat /tmp/ultraprompt-claude-plugin-update.log
    echo "✓ Claude Code plugin cache updated"
  elif claude plugins install ultraprompt@local-marketplace >/tmp/ultraprompt-claude-plugin-install.log 2>&1; then
    cat /tmp/ultraprompt-claude-plugin-install.log
    echo "✓ Claude Code plugin cache installed"
  else
    echo "WARN: Claude Code plugin cache refresh failed; inspect /tmp/ultraprompt-claude-plugin-update.log and /tmp/ultraprompt-claude-plugin-install.log"
  fi
fi

echo "✓ Installed at: $TARGET"
echo "✓ Backup at:    $BACKUP_DIR"
echo
echo "Next: restart Claude Code, then run /mcp to verify ultraprompt-meta connects."
echo "Optional: /ultraprompt:install-monitor to enable launchd between-session safety."
