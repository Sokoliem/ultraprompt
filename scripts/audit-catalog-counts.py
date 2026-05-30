#!/usr/bin/env python3
"""V9.3 — Catalog-count drift guard.

v9.2 made the *version* self-enforcing across every site, but catalog *counts*
(skills, agents, MCP tools, …) were only guarded where they are rendered from a
template. Counts that live as hand-written literals could silently drift:

  - `dist/catalog-metadata.json` going stale vs the actual files on disk, and
  - the hard-coded fallback dict in `hooks/recipes/session-bootstrap.py`, which
    feeds the SessionStart banner whenever catalog-metadata is unreadable (the
    exact class of bug fixed reactively in V9.1).

This guard recomputes every count from disk (reusing build-catalog-metadata's
own `build()` so there is a single counting implementation) and asserts those
literal sites agree. Exit 1 on any mismatch. Rendered sites (plugin.json,
README, menu, dashboard, INSTALL) are already covered by
render-manifest-template --check.

Usage:
  python3 scripts/audit-catalog-counts.py
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {rel}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def disk_counts() -> dict[str, int]:
    """Ground-truth counts, computed from disk by build-catalog-metadata.build()."""
    builder = _load_module("build_catalog_metadata", "scripts/build-catalog-metadata.py")
    return dict(builder.build()["counts"])


def catalog_metadata_counts() -> dict[str, int] | None:
    path = ROOT / "dist" / "catalog-metadata.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("counts") if isinstance(data, dict) else None


def session_bootstrap_defaults() -> dict[str, int] | None:
    """Extract the hard-coded fallback dict from the SessionStart banner hook."""
    path = ROOT / "hooks" / "recipes" / "session-bootstrap.py"
    text = path.read_text(encoding="utf-8")
    match = re.search(r"defaults\s*=\s*(\{.*?\})", text, re.DOTALL)
    if not match:
        return None
    try:
        value = ast.literal_eval(match.group(1))
    except Exception:
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    problems: list[str] = []
    disk = disk_counts()

    # 1. dist/catalog-metadata.json must match disk (freshness).
    meta = catalog_metadata_counts()
    if meta is None:
        problems.append("dist/catalog-metadata.json: missing or unreadable counts (run scripts/build-catalog-metadata.py)")
    else:
        for key, expected in disk.items():
            actual = meta.get(key)
            if actual != expected:
                problems.append(
                    f"dist/catalog-metadata.json counts.{key}={actual} != disk {expected} "
                    "(run scripts/build-catalog-metadata.py)"
                )

    # 2. session-bootstrap.py fallback dict must match disk for every key it carries.
    defaults = session_bootstrap_defaults()
    if defaults is None:
        problems.append("hooks/recipes/session-bootstrap.py: could not parse `defaults` fallback dict")
    else:
        for key, value in defaults.items():
            expected = disk.get(key)
            if expected is None:
                problems.append(f"session-bootstrap.py defaults has unknown key {key!r}")
            elif value != expected:
                problems.append(
                    f"session-bootstrap.py defaults[{key!r}]={value} != disk {expected} "
                    "(update the fallback dict to match the catalog)"
                )

    if problems:
        print("Catalog-count drift detected:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    summary = ", ".join(f"{k}={v}" for k, v in sorted(disk.items()))
    print(f"Catalog counts consistent across disk, catalog-metadata, and session-bootstrap fallback ({summary}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
