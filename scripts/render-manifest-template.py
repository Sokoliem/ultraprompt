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
VERSION_FILE = ROOT / "VERSION"
CHANGELOG = ROOT / "CHANGELOG.md"

TEMPLATES: list[tuple[Path, Path]] = [
    (ROOT / ".claude-plugin" / "plugin.json.tmpl", ROOT / ".claude-plugin" / "plugin.json"),
    (ROOT / ".claude-plugin" / "marketplace.json.tmpl", ROOT / ".claude-plugin" / "marketplace.json"),
    (ROOT / "commands" / "menu.md.tmpl", ROOT / "commands" / "menu.md"),
    (ROOT / "commands" / "dashboard.md.tmpl", ROOT / "commands" / "dashboard.md"),
    (ROOT / "README.md.tmpl", ROOT / "README.md"),
]

# Version sites that are NOT rendered from a .tmpl and so must be asserted equal
# to the VERSION file by the drift guard. Each entry is (relative path, JSON
# pointer-ish accessor name) where the accessor knows how to dig out the version.
_HAND_MAINTAINED_VERSION_FILES = (".codex-plugin/plugin.json",)
# Rendered manifests whose on-disk version must match VERSION (catches an
# un-regenerated tree even though the .tmpl now sources ${version}).
_RENDERED_VERSION_FILES = (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json")


def read_version() -> str:
    """Single source of truth for the plugin version."""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def changelog_top_version() -> str | None:
    """Most recent released version from the CHANGELOG (`## [x.y.z]`)."""
    if not CHANGELOG.exists():
        return None
    match = re.search(r"^##\s*\[(\d+\.\d+\.\d+)\]", CHANGELOG.read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def _manifest_version(data: dict) -> str | None:
    if "version" in data:
        return data.get("version")
    plugins = data.get("plugins")
    if isinstance(plugins, list) and plugins:
        return plugins[0].get("version")
    return None


def check_versions(version: str) -> list[str]:
    """Return drift messages if any version site disagrees with the VERSION file.

    This is the guard the old `--check` lacked: previously the .tmpl hard-coded
    the version, so a stale release bump rendered cleanly and CI stayed green.
    """
    problems: list[str] = []
    top = changelog_top_version()
    if top != version:
        problems.append(f"CHANGELOG.md top entry is [{top}], expected [{version}] (VERSION file)")
    for rel in _HAND_MAINTAINED_VERSION_FILES + _RENDERED_VERSION_FILES:
        path = ROOT / rel
        try:
            actual = _manifest_version(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 — report unreadable/invalid manifests as drift
            problems.append(f"{rel}: unreadable ({exc})")
            continue
        if actual != version:
            hint = "run scripts/render-manifest-template.py" if rel in _RENDERED_VERSION_FILES else "bump by hand to match VERSION"
            problems.append(f"{rel} version {actual!r} != {version!r} ({hint})")
    return problems


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


def token_map(counts: dict[str, int], version: str) -> dict[str, str]:
    """Map dotted token names (with safe-name flattened via underscore) to string values."""
    version_mm = ".".join(version.split(".")[:2])  # "9.2.0" -> "9.2" for prose like "V9.2"
    base = {
        "version": version,
        "version_mm": version_mm,
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

    if not VERSION_FILE.exists():
        print(f"ERROR: {VERSION_FILE.relative_to(ROOT)} missing — it is the single source of truth for the plugin version.", file=sys.stderr)
        return 1

    version = read_version()
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    counts = catalog.get("counts", {})
    tokens = token_map(counts, version)

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
        version_drift = check_versions(version)
        if drift or version_drift:
            if drift:
                print("Manifest template drift:", file=sys.stderr)
                for d in drift:
                    print(f"  - {d}", file=sys.stderr)
            if version_drift:
                print(f"Version drift (VERSION file = {version}):", file=sys.stderr)
                for d in version_drift:
                    print(f"  - {d}", file=sys.stderr)
            return 1
        print(f"Verified {rendered_count} manifests in sync with templates; version {version} consistent across all sites.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
