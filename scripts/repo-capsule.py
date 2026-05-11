#!/usr/bin/env python3
"""Generate a compact repository contract capsule. Includes cache + drift support.

Cache key: repo_root + git rev-parse HEAD. Stored under
${CLAUDE_PLUGIN_DATA}/capsules/<sha>.json. Drift compares two capsules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_FILE_BYTES = 300_000

KNOWN_FILES = [
    "CLAUDE.md", "AGENTS.md", ".cursorrules", ".windsurfrules", "CONTRIBUTING.md", "README.md", "README.rst",
    "package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lockb", "bun.lock",
    "pyproject.toml", "requirements.txt", "poetry.lock", "Pipfile", "Pipfile.lock", "uv.lock",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
    "pom.xml", "build.gradle", "build.gradle.kts", "Makefile", "justfile", "Taskfile.yml",
    "Dockerfile", "docker-compose.yml", "compose.yml", "CODEOWNERS", ".github/CODEOWNERS",
]
CONFIG_PATTERNS = [
    "tsconfig*.json", "eslint.config.*", ".eslintrc*", "prettier.config.*", ".prettierrc*",
    "vitest.config.*", "jest.config.*", "pytest.ini", "tox.ini", "mypy.ini", "ruff.toml", ".ruff.toml",
    "terraform*.tf", "helmfile.*", "Chart.yaml", "next.config.*", "vite.config.*", "turbo.json", "nx.json",
]
SENSITIVE_PATTERNS = [
    ".env", ".env.*", "*.pem", "*.key", "id_rsa", "id_ed25519", "secrets.json", "secrets.yaml", "secret.yaml",
]
MIGRATION_DIR_NAMES = {"migrations", "migration", "db/migrate", "prisma/migrations", "alembic/versions"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def rel(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except Exception:
        return path.as_posix()


def find_files(root: Path, pattern: str, limit: int = 50) -> list[str]:
    try:
        return sorted(rel(p, root) for p in root.glob(pattern) if p.exists())[:limit]
    except Exception:
        return []


def detect_package_managers(root: Path) -> list[str]:
    checks = [
        ("pnpm", "pnpm-lock.yaml"), ("yarn", "yarn.lock"), ("npm", "package-lock.json"),
        ("bun", "bun.lockb"), ("bun", "bun.lock"),
        ("poetry", "poetry.lock"), ("uv", "uv.lock"), ("pip", "requirements.txt"),
        ("cargo", "Cargo.lock"), ("go", "go.mod"), ("bundler", "Gemfile.lock"),
        ("composer", "composer.lock"), ("maven", "pom.xml"),
        ("gradle", "build.gradle"), ("gradle", "build.gradle.kts"),
    ]
    found: list[str] = []
    for name, file in checks:
        if (root / file).exists() and name not in found:
            found.append(name)
    if (root / "package.json").exists() and not any(x in found for x in ["npm", "pnpm", "yarn", "bun"]):
        found.append("npm")
    return found


def parse_package_json(root: Path) -> dict[str, Any]:
    p = root / "package.json"
    if not p.exists():
        return {}
    try:
        data = json.loads(read_text(p))
    except Exception:
        return {"path": "package.json", "error": "invalid JSON"}
    scripts = data.get("scripts", {}) if isinstance(data.get("scripts"), dict) else {}
    useful = {}
    for k in sorted(scripts):
        if re.search(r"test|lint|type|check|build|format|dev|start|release|publish", k, flags=re.I):
            useful[k] = scripts[k]
    return {"path": "package.json", "name": data.get("name"), "type": data.get("type"), "scripts": useful}


def detect_commands(root: Path) -> dict[str, list[str]]:
    managers = detect_package_managers(root)
    pkg = parse_package_json(root)
    scripts = pkg.get("scripts", {}) if isinstance(pkg.get("scripts"), dict) else {}
    test_cmds: list[str] = []
    lint_cmds: list[str] = []
    typecheck_cmds: list[str] = []
    build_cmds: list[str] = []
    for k in scripts:
        manager = managers[0] if managers and managers[0] in {"npm", "pnpm", "yarn", "bun"} else "npm"
        cmd = f"{manager} run {k}"
        kl = k.lower()
        if "test" in kl:
            test_cmds.append(cmd)
        if "lint" in kl:
            lint_cmds.append(cmd)
        if "type" in kl or "tsc" in kl:
            typecheck_cmds.append(cmd)
        if "build" in kl:
            build_cmds.append(cmd)
    if (root / "pyproject.toml").exists():
        test_cmds.append("pytest")
    if (root / "Cargo.toml").exists():
        test_cmds.append("cargo test")
        build_cmds.append("cargo build")
    if (root / "go.mod").exists():
        test_cmds.append("go test ./...")
        build_cmds.append("go build ./...")
    if (root / "Makefile").exists():
        test_cmds.append("make test")
        build_cmds.append("make build")
    return {
        "test": sorted(set(test_cmds)),
        "lint": sorted(set(lint_cmds)),
        "typecheck": sorted(set(typecheck_cmds)),
        "build": sorted(set(build_cmds)),
    }


def detect_ci(root: Path) -> list[str]:
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return []
    return sorted(rel(p, root) for p in workflows.glob("*.y*ml"))


def detect_configs(root: Path) -> list[str]:
    out: list[str] = []
    for pat in CONFIG_PATTERNS:
        out.extend(find_files(root, pat, 20))
    return sorted(set(out))


def detect_sensitive(root: Path) -> list[str]:
    out: list[str] = []
    for pat in SENSITIVE_PATTERNS:
        out.extend(find_files(root, pat, 20))
        out.extend(find_files(root, f"**/{pat}", 20))
    return sorted(set(out))


def detect_migrations(root: Path) -> list[str]:
    out: list[str] = []
    for d in MIGRATION_DIR_NAMES:
        p = root / d
        if p.is_dir():
            out.append(rel(p, root))
    return sorted(out)


def detect_known_files(root: Path) -> list[str]:
    return sorted(rel(root / f, root) for f in KNOWN_FILES if (root / f).exists())


def git_head(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(root), text=True,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def build_capsule(target: Path) -> dict[str, Any]:
    target = target.resolve()
    return {
        "generated_at": now_iso(),
        "repo": str(target),
        "git_head": git_head(target),
        "guidance_files": detect_known_files(target),
        "package_managers": detect_package_managers(target),
        "package_json": parse_package_json(target),
        "validation_commands": detect_commands(target),
        "ci_workflows": detect_ci(target),
        "config_files": detect_configs(target),
        "migration_dirs": detect_migrations(target),
        "sensitive_paths": detect_sensitive(target),
    }


# -------------------- caching --------------------

def cache_dir() -> Path:
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    if base:
        return Path(base).expanduser().resolve() / "capsules"
    return Path.home() / ".claude" / "plugins" / "data" / "ultraprompt" / "capsules"


def cache_key(repo_root: Path, head: str) -> str:
    h = hashlib.sha256(f"{repo_root.resolve()}|{head}".encode("utf-8")).hexdigest()[:16]
    return h


def cached_capsule_path(repo_root: Path, head: str) -> Path:
    return cache_dir() / f"{cache_key(repo_root, head)}.json"


def capsule_with_cache(path: str | Path, *, force_refresh: bool = False) -> tuple[dict[str, Any], bool]:
    target = Path(path).resolve()
    head = git_head(target)
    cache_path = cached_capsule_path(target, head) if head else None
    if not force_refresh and cache_path and cache_path.exists():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8")), True
        except Exception:
            pass
    capsule = build_capsule(target)
    if cache_path:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(capsule, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            pass
    return capsule, False


def capsule_at_commit(repo_root: Path, commit: str) -> dict[str, Any] | None:
    """Build a capsule as it was at a specific commit. Best-effort using a worktree."""
    repo_root = repo_root.resolve()
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            wt = Path(tmp) / "wt"
            r = subprocess.run(
                ["git", "worktree", "add", "--detach", str(wt), commit],
                cwd=str(repo_root), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            )
            if r.returncode != 0:
                return None
            try:
                return build_capsule(wt)
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(wt)],
                    cwd=str(repo_root), text=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
                )
    except Exception:
        return None


def diff_lists(prev: list[str], curr: list[str]) -> dict[str, list[str]]:
    pset, cset = set(prev or []), set(curr or [])
    return {"added": sorted(cset - pset), "removed": sorted(pset - cset)}


def diff_dicts(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    pset, cset = set((prev or {}).keys()), set((curr or {}).keys())
    out: dict[str, Any] = {
        "added_keys": sorted(cset - pset),
        "removed_keys": sorted(pset - cset),
        "changed": {},
    }
    for k in pset & cset:
        if prev.get(k) != curr.get(k):
            out["changed"][k] = {"before": prev.get(k), "after": curr.get(k)}
    return out


def capsule_diff(path: str | Path, since_commit: str) -> dict[str, Any]:
    target = Path(path).resolve()
    current, _ = capsule_with_cache(target)
    prior = capsule_at_commit(target, since_commit)
    if prior is None:
        return {
            "since_commit": since_commit,
            "error": f"could not build capsule at commit {since_commit}",
            "current": current,
        }
    return {
        "since_commit": since_commit,
        "current_head": current.get("git_head"),
        "guidance_files": diff_lists(prior.get("guidance_files", []), current.get("guidance_files", [])),
        "package_managers": diff_lists(prior.get("package_managers", []), current.get("package_managers", [])),
        "validation_commands": {
            kind: diff_lists(prior.get("validation_commands", {}).get(kind, []),
                             current.get("validation_commands", {}).get(kind, []))
            for kind in ("test", "lint", "typecheck", "build")
        },
        "ci_workflows": diff_lists(prior.get("ci_workflows", []), current.get("ci_workflows", [])),
        "config_files": diff_lists(prior.get("config_files", []), current.get("config_files", [])),
        "migration_dirs": diff_lists(prior.get("migration_dirs", []), current.get("migration_dirs", [])),
        "sensitive_paths": diff_lists(prior.get("sensitive_paths", []), current.get("sensitive_paths", [])),
        "package_json_scripts": diff_dicts(
            (prior.get("package_json") or {}).get("scripts", {}) or {},
            (current.get("package_json") or {}).get("scripts", {}) or {},
        ),
    }


def render_markdown(capsule: dict[str, Any]) -> str:
    lines = [f"# Repo capsule: {capsule['repo']}"]
    if capsule.get("git_head"):
        lines.append(f"git HEAD: `{capsule['git_head'][:12]}`")
    lines.append(f"generated_at: {capsule['generated_at']}")
    lines.append("")

    def section(title: str, items: list[str]) -> None:
        lines.append(f"## {title}")
        if not items:
            lines.append("(none)")
        else:
            for i in items:
                lines.append(f"- `{i}`")
        lines.append("")

    section("Guidance files", capsule.get("guidance_files", []))
    lines.append("## Package managers")
    lines.append(", ".join(capsule.get("package_managers") or []) or "(none)")
    lines.append("")
    cmds = capsule.get("validation_commands", {})
    lines.append("## Validation commands")
    for k in ("test", "lint", "typecheck", "build"):
        v = cmds.get(k, [])
        if v:
            lines.append(f"- {k}: " + ", ".join(f"`{c}`" for c in v))
    lines.append("")
    section("CI workflows", capsule.get("ci_workflows", []))
    section("Config files", capsule.get("config_files", []))
    section("Migration dirs", capsule.get("migration_dirs", []))
    section("Sensitive paths", capsule.get("sensitive_paths", []))
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--diff-since", help="commit-ish to diff against")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    if args.diff_since:
        diff = capsule_diff(repo, args.diff_since)
        print(json.dumps(diff, indent=2, sort_keys=True))
        return 0
    capsule, _hit = capsule_with_cache(repo, force_refresh=args.force_refresh)
    if args.format == "json":
        print(json.dumps(capsule, indent=2, sort_keys=True))
    else:
        print(render_markdown(capsule))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
