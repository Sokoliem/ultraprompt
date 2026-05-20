#!/usr/bin/env python3
"""Build/check dist/routing-policy.json from source skill metadata."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from routing_policy import write_routing_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify generated routing policy is current")
    args = parser.parse_args()
    target = write_routing_policy(ROOT, check=args.check)
    if args.check:
        print(f"Routing policy OK: {target.relative_to(ROOT)}")
    else:
        print(f"Wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
