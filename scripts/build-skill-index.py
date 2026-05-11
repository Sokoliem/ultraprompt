#!/usr/bin/env python3
"""Build dist/skill-index.json from skill, command, and agent frontmatter.

Run: python3 scripts/build-skill-index.py [--check]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ultraprompt_index import write_index


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Verify the index is up to date")
    args = parser.parse_args()
    target = write_index(ROOT, check=args.check)
    if args.check:
        print(f"Index OK: {target.relative_to(ROOT)}")
    else:
        print(f"Wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
