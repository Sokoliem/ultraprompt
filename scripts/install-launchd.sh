#!/usr/bin/env bash
# V8 launchd installer for worktree-monitor.
set -euo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/marketplaces/local-marketplace/ultraprompt}"
LABEL="com.ultraprompt.worktree-monitor"
DIGEST_LABEL="com.ultraprompt.worktree-monitor-digest"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/$LABEL.plist"
DIGEST_PLIST="$PLIST_DIR/$DIGEST_LABEL.plist"
LOG_DIR="$HOME/.claude/ultraprompt-data"
mkdir -p "$LOG_DIR" "$PLIST_DIR"
INTERVAL_SEC=${ULTRAPROMPT_MONITOR_INTERVAL:-1800}
cmd="${1:-install}"

write_scan() {
cat > "$PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$PLUGIN_ROOT/scripts/worktree-monitor.py</string>
    <string>--mode</string><string>scan</string>
    <string>--quiet</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CLAUDE_PLUGIN_ROOT</key><string>$PLUGIN_ROOT</string>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartInterval</key><integer>$INTERVAL_SEC</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOG_DIR/launchd-monitor.out</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launchd-monitor.err</string>
</dict></plist>
XML
}

write_digest() {
cat > "$DIGEST_PLIST" <<XML
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$DIGEST_LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>$PLUGIN_ROOT/scripts/worktree-monitor.py</string>
    <string>--mode</string><string>digest</string>
    <string>--quiet</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>CLAUDE_PLUGIN_ROOT</key><string>$PLUGIN_ROOT</string>
    <key>HOME</key><string>$HOME</string>
    <key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>$LOG_DIR/launchd-digest.out</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launchd-digest.err</string>
</dict></plist>
XML
}

case "$cmd" in
  install)
    [ -f "$PLIST" ] && cp "$PLIST" "$PLIST.bak" && launchctl unload "$PLIST" 2>/dev/null || true
    write_scan; write_digest
    launchctl load "$PLIST"; launchctl load "$DIGEST_PLIST"
    echo "✓ Installed: $PLIST (every ${INTERVAL_SEC}s)"
    echo "✓ Installed: $DIGEST_PLIST (daily 09:00)"
    echo "Logs: $LOG_DIR/launchd-monitor.{out,err}"
    echo "Verify: launchctl list | grep ultraprompt"
    ;;
  uninstall)
    [ -f "$PLIST" ] && launchctl unload "$PLIST" 2>/dev/null && rm -f "$PLIST" && echo "✓ Uninstalled $LABEL"
    [ -f "$DIGEST_PLIST" ] && launchctl unload "$DIGEST_PLIST" 2>/dev/null && rm -f "$DIGEST_PLIST" && echo "✓ Uninstalled $DIGEST_LABEL"
    ;;
  status)
    echo "=== launchd ==="; launchctl list | grep ultraprompt || echo "(none)"
    echo; echo "=== plists ==="; ls -la "$PLIST" "$DIGEST_PLIST" 2>/dev/null || echo "(none)"
    [ -f "$LOG_DIR/launchd-monitor.out" ] && echo && echo "=== last out ===" && tail -10 "$LOG_DIR/launchd-monitor.out"
    [ -f "$LOG_DIR/launchd-monitor.err" ] && [ -s "$LOG_DIR/launchd-monitor.err" ] && echo && echo "=== last err ===" && tail -5 "$LOG_DIR/launchd-monitor.err"
    ;;
  *)
    echo "usage: $0 {install|uninstall|status}"; exit 1 ;;
esac
