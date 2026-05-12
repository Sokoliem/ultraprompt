#!/usr/bin/env bash
# V8 unified installer. Usage: install.sh [claude-code|codex|both]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
target="${1:-both}"
case "$target" in
  claude-code) bash "$HERE/install-claude-code.sh" ;;
  codex) bash "$HERE/install-codex.sh" ;;
  both)
    bash "$HERE/install-claude-code.sh"
    echo
    echo "============================================="
    echo
    bash "$HERE/install-codex.sh"
    ;;
  *) echo "usage: $0 [claude-code|codex|both]"; exit 1 ;;
esac
