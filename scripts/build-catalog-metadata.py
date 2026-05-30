#!/usr/bin/env python3
"""Build/check a compact catalog metadata snapshot for release gates."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "catalog-metadata.json"


def load_json(rel: str) -> Any:
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    data: dict[str, str] = {}
    current_key = None
    current_value: list[str] = []
    for line in match.group(1).splitlines():
        if re.match(r"^[A-Za-z0-9_-]+:\s*", line):
            if current_key:
                data[current_key] = "\n".join(current_value).strip()
            current_key, value = line.split(":", 1)
            current_key = current_key.strip()
            current_value = [value.strip()]
        elif current_key:
            current_value.append(line)
    if current_key:
        data[current_key] = "\n".join(current_value).strip()
    return data


def plugin_version() -> str:
    return str(load_json(".claude-plugin/plugin.json").get("version", "unknown"))


def mcp_tool_count() -> int:
    path = ROOT / "mcp" / "ultraprompt_meta.py"
    spec = importlib.util.spec_from_file_location("ultraprompt_meta", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.TOOLS)


def artifact_schema_count() -> int:
    """Number of registered artifact validators (``artifact-validate.SCHEMAS``).

    This is intentionally broader than ``ls artifact-schemas/*.json``: that
    directory holds only the standalone JSON Schema files, whereas ``SCHEMAS``
    is the full registry of artifact types the validator enforces (including
    schemas defined inline). The registry count is the user-facing number, so
    it is what the manifests and README advertise.
    """
    path = ROOT / "scripts" / "artifact-validate.py"
    spec = importlib.util.spec_from_file_location("artifact_validate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return len(module.SCHEMAS)


def file_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        if path.is_file():
            digest.update(str(path.relative_to(ROOT)).replace("\\", "/").encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def build() -> dict[str, Any]:
    skill_specs = load_json("source/skill-specs.json")
    agent_specs = load_json("source/agent-specs.json")
    panel_specs = load_json("source/panel-specs.json")
    hooks = load_json("hooks/hooks.json")
    commands = sorted((ROOT / "commands").glob("*.md"))
    agents = sorted((ROOT / "agents").glob("*.md"))
    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    styles = sorted((ROOT / "output-styles").glob("*.md"))
    artifact_schema_files = sorted((ROOT / "artifact-schemas").glob("*.json"))
    source_paths = [
        ROOT / "source" / "catalog" / "catalog.json",
        ROOT / "source" / "skill-specs.json",
        ROOT / "source" / "agent-specs.json",
        ROOT / "source" / "panel-specs.json",
        ROOT / "source" / "dream-jobs.json",
        ROOT / "source" / "memory-schemas.json",
        ROOT / "hooks" / "hooks.json",
        ROOT / "mcp" / "ultraprompt_meta.py",
        ROOT / "scripts" / "artifact-validate.py",
        ROOT / "scripts" / "build-capability-graph.py",
        ROOT / "scripts" / "pathfinder.py",
        ROOT / "scripts" / "memory-store.py",
        ROOT / "scripts" / "dream-runner.py",
        ROOT / "scripts" / "learning-queue.py",
        ROOT / "scripts" / "cognitive-event-log.py",
    ] + commands + styles + artifact_schema_files
    return {
        "schema_version": 1,
        "plugin_version": plugin_version(),
        "counts": {
            "skills": len(skills),
            "skill_specs": len(skill_specs),
            "agents": len(agents),
            "agent_specs": len(agent_specs),
            "commands": len(commands),
            "panels": len(panel_specs),
            "mcp_tools": mcp_tool_count(),
            "artifact_schemas": artifact_schema_count(),
            "output_styles": len(styles),
            "registered_hooks": sum(
                len(group.get("hooks", []))
                for groups in (hooks.get("hooks") or {}).values()
                for group in groups
            ),
        },
        "tiers": {
            "core": sum(1 for s in skill_specs if s.get("tier") == "core"),
            "specialist": sum(1 for s in skill_specs if s.get("tier") == "specialist"),
            "ecosystem": sum(1 for s in skill_specs if s.get("tier") == "ecosystem"),
        },
        "skills": [s.get("name") for s in skill_specs],
        "agents": [parse_frontmatter(p).get("name", p.stem) for p in agents],
        "source_hash": file_hash(source_paths),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify dist/catalog-metadata.json is current")
    args = parser.parse_args()
    metadata = build()
    text = json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("dist/catalog-metadata.json is stale; run scripts/build-catalog-metadata.py")
            return 1
        print("dist/catalog-metadata.json is current.")
        return 0
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
