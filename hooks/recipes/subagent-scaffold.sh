#!/usr/bin/env bash
# Thin delegator — the payload lives in subagent-scaffold.py (single source of
# truth for both POSIX and Windows). Fails open if python3 is unavailable so a
# scaffold hook can never block a subagent from starting.
exec python3 "$(dirname "$0")/subagent-scaffold.py" 2>/dev/null || exit 0
