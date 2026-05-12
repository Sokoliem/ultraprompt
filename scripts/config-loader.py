#!/usr/bin/env python3
"""Layered config loader. Defaults < user TOML < project TOML < env vars."""
from __future__ import annotations
import os, re, sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = ROOT / "source" / "config-defaults.toml"
USER_CONFIG_PATH = Path.home() / ".claude" / "ultraprompt.toml"


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.lower() in ("true", "false"):
        return raw.lower() == "true"
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        return raw[1:-1]
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_parse_value(p.strip()) for p in inner.split(",")]
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_toml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current: str | None = None
    for line in text.splitlines():
        line = re.sub(r"#.*$", "", line).strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip()
            result.setdefault(current, {})
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        v = _parse_value(value.strip())
        if current is None:
            result[key.strip()] = v
        else:
            result[current][key.strip()] = v
    return result



def _parse_env_overrides_v8(env: dict) -> tuple[dict, list[str]]:
    """V8: Parse env overrides using ULTRAPROMPT__SECTION__KEY=value syntax.

    Single-underscore syntax (ULTRAPROMPT_AUTO_WIP_SAVE_ENABLED) is ambiguous
    when keys themselves contain underscores. V8 prefers double-underscore as section
    separator. Single-underscore variables emit a deprecation warning but still parse
    using a best-effort fallback.
    """
    overrides = {}
    warnings = []
    for k, v in env.items():
        if not k.startswith("ULTRAPROMPT"):
            continue
        # V8 preferred: ULTRAPROMPT__SECTION__KEY
        if "__" in k:
            parts = k.replace("ULTRAPROMPT__", "").split("__")
            if len(parts) >= 2:
                section = parts[0].lower()
                key = "_".join(parts[1:]).lower()
                overrides.setdefault(section, {})[key] = _coerce_env(v)
                continue
        # Legacy single-underscore: emit warning unless it's ULTRAPROMPT_DISABLE_HOOKS or similar known flat key
        legacy = k.replace("ULTRAPROMPT_", "").lower()
        if legacy in ("disable_hooks",):
            overrides[legacy] = _coerce_env(v)
        else:
            warnings.append(f"{k} uses legacy single-underscore syntax; prefer ULTRAPROMPT__SECTION__KEY")
            # Best-effort fallback: split at first underscore
            if "_" in legacy:
                sec, _, rest = legacy.partition("_")
                overrides.setdefault(sec, {})[rest] = _coerce_env(v)
            else:
                overrides[legacy] = _coerce_env(v)
    return overrides, warnings


def _coerce_env(v):
    """Convert env string to bool/int/float/string."""
    if isinstance(v, str):
        if v.lower() in ("true", "yes", "1", "on"):
            return True
        if v.lower() in ("false", "no", "0", "off"):
            return False
        try:
            if "." in v: return float(v)
            return int(v)
        except ValueError:
            return v
    return v


def _merge_layer(config: dict[str, Any], layer: dict[str, Any]) -> dict[str, Any]:
    """Merge one config layer into another, preserving nested sections."""
    for section, value in layer.items():
        if isinstance(value, dict):
            config.setdefault(section, {})
            if isinstance(config[section], dict):
                config[section].update(value)
            else:
                config[section] = value
        else:
            config[section] = value
    return config


def load_config(repo_root: Path | None = None) -> dict[str, Any]:
    config: dict[str, Any] = {}
    if DEFAULTS_PATH.exists():
        config = parse_toml(DEFAULTS_PATH.read_text(encoding="utf-8"))
    if USER_CONFIG_PATH.exists():
        _merge_layer(config, parse_toml(USER_CONFIG_PATH.read_text(encoding="utf-8")))
    if repo_root:
        pp = repo_root / ".claude" / "ultraprompt.toml"
        if pp.exists():
            _merge_layer(config, parse_toml(pp.read_text(encoding="utf-8")))
    env_overrides, warnings = _parse_env_overrides_v8(os.environ)
    _merge_layer(config, env_overrides)
    if warnings and os.environ.get("ULTRAPROMPT_CONFIG_WARNINGS", "").lower() in ("1", "true", "yes", "on"):
        config.setdefault("_warnings", []).extend(warnings)
    return config


def get(config: dict, path: str, default: Any = None) -> Any:
    cur: Any = config
    for p in path.split("."):
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def main() -> int:
    import json
    repo = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    print(json.dumps(load_config(repo), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
