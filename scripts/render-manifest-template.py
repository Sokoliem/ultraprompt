#!/usr/bin/env python3
"""V8.8 (S2) — Render manifest templates from .tmpl source files.

Substitutes `${catalog.X}` tokens against `dist/catalog-metadata.json`, then writes
the rendered output to its declared destination. Eliminates hand-typed catalog
counts across plugin.json, marketplace.json, menu.md, and dashboard.md.

Tokens (from `counts` dict in dist/catalog-metadata.json):
  catalog.skills            -> skills count
  catalog.agents            -> agents count
  catalog.mcp_tools         -> mcp_tools count
  catalog.commands          -> commands count
  catalog.panels            -> panels count
  catalog.artifact_schemas  -> artifact_schemas count
  catalog.output_styles     -> output_styles count
  catalog.registered_hooks  -> registered_hooks count

Usage:
  python3 scripts/render-manifest-template.py            # render all
  python3 scripts/render-manifest-template.py --check    # exit 1 if rendered != on-disk

Telemetry: emits a `template-render` event per PRD §10.2.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "dist" / "catalog-metadata.json"

TEMPLATES: list[tuple[Path, Path]] = [
    (ROOT / ".claude-plugin" / "plugin.json.tmpl", ROOT / ".claude-plugin" / "plugin.json"),
    (ROOT / ".claude-plugin" / "marketplace.json.tmpl", ROOT / ".claude-plugin" / "marketplace.json"),
    (ROOT / "commands" / "menu.md.tmpl", ROOT / "commands" / "menu.md"),
    (ROOT / "commands" / "dashboard.md.tmpl", ROOT / "commands" / "dashboard.md"),
]


def _ledger_write(event_type: str, **fields) -> None:
    if os.environ.get("ULTRAPROMPT_DISABLE_TELEMETRY") == "1":
        return
    try:
        spec = importlib.util.spec_from_file_location("led", ROOT / "scripts" / "ledger-v2.py")
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.write_event(event_type, **fields)
    except Exception:
        pass


def token_map(counts: dict[str, int]) -> dict[str, str]:
    """Map dotted token names (with safe-name flattened via underscore) to string values."""
    base = {
        "catalog_skills": counts.get("skills", 0),
        "catalog_agents": counts.get("agents", 0),
        "catalog_mcp_tools": counts.get("mcp_tools", 0),
        "catalog_commands": counts.get("commands", 0),
        "catalog_panels": counts.get("panels", 0),
        "catalog_artifact_schemas": counts.get("artifact_schemas", 0),
        "catalog_output_styles": counts.get("output_styles", 0),
        "catalog_registered_hooks": counts.get("registered_hooks", 0),
    }
    return {k: str(v) for k, v in base.items()}


def render_template(tmpl_path: Path, tokens: dict[str, str]) -> str:
    """Render with both ${catalog.X} (PRD syntax) and ${catalog_X} (Template-safe)."""
    text = tmpl_path.read_text(encoding="utf-8")
    # PRD-style dotted tokens first: ${catalog.skills} -> ${catalog_skills}
    text = re.sub(r"\$\{catalog\.([a-z_]+)\}", r"${catalog_\1}", text)
    rendered = Template(text).safe_substitute(tokens)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="exit 1 if rendered output != on-disk")
    args = parser.parse_args()

    if not CATALOG.exists():
        print(f"ERROR: {CATALOG.relative_to(ROOT)} missing. Run scripts/build-catalog-metadata.py first.", file=sys.stderr)
        return 1

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    counts = catalog.get("counts", {})
    tokens = token_map(counts)

    start = time.time()
    drift: list[str] = []
    rendered_count = 0

    for tmpl_path, dest_path in TEMPLATES:
        if not tmpl_path.exists():
            # If the .tmpl is missing, fall back to leaving the dest in place.
            continue
        rendered = render_template(tmpl_path, tokens)
        rendered_count += 1
        if args.check:
            existing = dest_path.read_text(encoding="utf-8") if dest_path.exists() else ""
            if existing != rendered:
                drift.append(f"{dest_path.relative_to(ROOT)} (regenerate via scripts/render-manifest-template.py)")
        else:
            dest_path.write_text(rendered, encoding="utf-8")
            print(f"Rendered {dest_path.relative_to(ROOT)}")

    duration_ms = int((time.time() - start) * 1000)
    _ledger_write(
        "template-render",
        templates_rendered=rendered_count,
        tokens_substituted=len(tokens),
        duration_ms=duration_ms,
        check_mode=args.check,
        drift_count=len(drift),
    )

    if args.check:
        if drift:
            print("Manifest template drift:", file=sys.stderr)
            for d in drift:
                print(f"  - {d}", file=sys.stderr)
            return 1
        print(f"Verified {rendered_count} manifests are in sync with templates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
