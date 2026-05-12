#!/usr/bin/env bash
# V8 Codex installer: backup, copy, preserve native Codex manifest, validate.
set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/.codex/local-marketplace/plugins/ultraprompt"
MARKET_DIR="$HOME/.codex/local-marketplace"
BACKUP_DIR="$HOME/.codex/local-marketplace/backups/ultraprompt-pre-v8-$(date +%Y%m%d-%H%M%S)"

echo "Ultraprompt V8 - Codex installer"
echo "Source: $SOURCE"
echo "Target: $TARGET"

# Backup existing
if [ -d "$TARGET" ]; then
  mkdir -p "$BACKUP_DIR"
  cp -R "$TARGET" "$BACKUP_DIR/ultraprompt"
  echo "✓ Backed up existing install: $BACKUP_DIR"
fi

if [ -f "$MARKET_DIR/.agents/plugins/marketplace.json" ]; then
  mkdir -p "$BACKUP_DIR"
  cp "$MARKET_DIR/.agents/plugins/marketplace.json" "$BACKUP_DIR/marketplace.json.before" 2>/dev/null || true
fi

# Copy plugin
mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
python3 "$SOURCE/scripts/package-plugin.py" --copy-to "$TARGET" >/dev/null

if [ ! -f "$TARGET/.codex-plugin/plugin.json" ]; then
  echo "ERROR: native Codex manifest missing: $TARGET/.codex-plugin/plugin.json" >&2
  exit 1
fi
if [ ! -f "$TARGET/.claude-plugin/plugin.json" ]; then
  echo "ERROR: Claude manifest missing: $TARGET/.claude-plugin/plugin.json" >&2
  exit 1
fi

# Preserve runtime-specific MCP variants. The Codex manifest declares
# ./.codex.mcp.json, while the Claude manifest declares ./.mcp.json.
if [ ! -f "$TARGET/.codex.mcp.json" ]; then
  echo "ERROR: Codex MCP config missing: $TARGET/.codex.mcp.json" >&2
  exit 1
fi
if [ ! -f "$TARGET/.mcp.json" ]; then
  echo "ERROR: Claude MCP config missing: $TARGET/.mcp.json" >&2
  exit 1
fi

# Ensure scripts executable
chmod +x "$TARGET/scripts/"*.py "$TARGET/scripts/"*.sh "$TARGET/hooks/recipes/"*.py "$TARGET/hooks/recipes/"*.sh "$TARGET/mcp/"*.py 2>/dev/null || true

# Update Codex marketplace catalog
mkdir -p "$MARKET_DIR/.agents/plugins"
cat > "$MARKET_DIR/.agents/plugins/marketplace.json" <<JSON
{
  "name": "local-marketplace",
  "interface": {"displayName": "Local Codex Plugins"},
  "plugins": [{
    "name": "ultraprompt",
    "source": {"source": "local", "path": "./plugins/ultraprompt"},
    "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
    "category": "Coding"
  }]
}
JSON

# Move stale cache aside so Codex re-caches from source
CACHE="$HOME/.codex/plugins/cache/local-marketplace/ultraprompt"
# V8: Codex's plugin loader checks ~/.codex/plugins/cache/<marketplace>/<plugin>/
# directly (no version subdir for local marketplaces). Source files alone are not
# enough — Codex needs the cache populated. Move stale cache aside, then copy fresh.
if [ -d "$CACHE" ] && [ "$(ls -A "$CACHE" 2>/dev/null)" ]; then
  mkdir -p "$BACKUP_DIR/cache-stale"
  cp -R "$CACHE/." "$BACKUP_DIR/cache-stale/" 2>/dev/null || true
  rm -rf "$CACHE"/*  "$CACHE"/.[!.]* 2>/dev/null || true
  echo "✓ Backed up stale Codex cache"
fi
# Codex looks at cache/<marketplace>/<plugin>/<version>/<plugin-files>.
# It enumerates subdirs of the plugin cache and treats each as a separate plugin
# version. Files placed directly under the plugin cache cause spurious "missing
# plugin.json" errors as Codex tries to load each subdir (tests/, agents/, etc.)
# as a plugin. Fix: place plugin contents under a version subdir (semver from
# plugin.json).
PLUGIN_VERSION=$(python3 -c "import json; print(json.load(open('$TARGET/.codex-plugin/plugin.json'))['version'])" 2>/dev/null || echo "current")
mkdir -p "$CACHE/$PLUGIN_VERSION"
python3 "$TARGET/scripts/package-plugin.py" --copy-to "$CACHE/$PLUGIN_VERSION" >/dev/null
echo "✓ Populated Codex cache at $CACHE/$PLUGIN_VERSION"

# V8: Force Codex to re-sync the local-marketplace by setting last_updated to old timestamp.
# Without this, Codex skips re-loading plugin source on restart even when files updated.
if [ -f "$HOME/.codex/config.toml" ]; then
  python3 - "$HOME/.codex/config.toml" <<'PYEOF' || true
import sys, re
from pathlib import Path
p = Path(sys.argv[1])
src = p.read_text()
pattern = re.compile(r'(\[marketplaces\.local-marketplace\]\s*\n)last_updated = "[^"]+"', re.MULTILINE)
new_src = pattern.sub(r'\1last_updated = "2024-01-01T00:00:00Z"', src)
if new_src != src:
    p.write_text(new_src)
    print("  ✓ Bumped local-marketplace last_updated to force Codex re-sync")
PYEOF
fi

# Ensure plugin enabled in config.toml
if [ -f "$HOME/.codex/config.toml" ]; then
  if ! grep -q 'plugins."ultraprompt@local-marketplace"' "$HOME/.codex/config.toml"; then
    echo "" >> "$HOME/.codex/config.toml"
    echo '[plugins."ultraprompt@local-marketplace"]' >> "$HOME/.codex/config.toml"
    echo 'enabled = true' >> "$HOME/.codex/config.toml"
    echo "✓ Added plugin enable to config.toml"
  fi
fi

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
python3 scripts/audit-manifest-schemas.py --runtime codex || echo "FAIL: schema audit"
python3 scripts/audit-manifest-schemas.py --runtime claude-code || echo "FAIL: Claude schema audit"
python3 scripts/validate-plugin.py 2>&1 | tail -8

echo
# V8: Write install manifest for atomic rollback (PRD §8.6)
PLUGIN_VERSION=$(python3 -c "import json; print(json.load(open('$TARGET/.codex-plugin/plugin.json'))['version'])" 2>/dev/null || echo "unknown")
python3 "$TARGET/scripts/install-manifest.py" write "$TARGET" --backup-root "$BACKUP_DIR" --plugin-version "$PLUGIN_VERSION" >/dev/null 2>&1     && echo "✓ Install manifest written"     || echo "  (manifest write skipped — non-blocking)"

echo "✓ Installed at: $TARGET"
echo "✓ Backup at:    $BACKUP_DIR"
echo
echo "Next: fully quit + relaunch Codex. /mcp should show ultraprompt-meta."
echo "Optional: /ultraprompt:install-monitor to enable launchd between-session safety."
