from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys


def extract_runtime_env_keys(config_path: Path) -> set[str]:
    text = config_path.read_text(encoding="utf-8")
    return set(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', text))


def extract_readme_env_mentions(readme_path: Path) -> set[str]:
    text = readme_path.read_text(encoding="utf-8")
    return set(re.findall(r"`([A-Z0-9_]+)`", text))


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    env_example = repo_root / ".env.example"
    env_production = repo_root / ".env.production.example"
    config_path = repo_root / "backend" / "app" / "core" / "config.py"
    readme_path = repo_root / "README.md"

    env_example_keys = parse_env_keys(env_example)
    env_production_keys = parse_env_keys(env_production)
    runtime_keys = extract_runtime_env_keys(config_path)
    readme_keys = extract_readme_env_mentions(readme_path)
    required_keys = runtime_keys | {"NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_WS_URL"}

    failures: list[str] = []
    missing_in_env_example = sorted(required_keys - env_example_keys)
    missing_in_env_production = sorted(required_keys - env_production_keys)
    missing_in_readme = sorted(required_keys - readme_keys)
    extra_in_production = sorted(env_production_keys - env_example_keys)
    missing_from_production = sorted(env_example_keys - env_production_keys)

    if missing_in_env_example:
        failures.append(
            ".env.example is missing runtime keys: " + ", ".join(missing_in_env_example)
        )
    if missing_in_env_production:
        failures.append(
            ".env.production.example is missing runtime keys: "
            + ", ".join(missing_in_env_production)
        )
    if missing_in_readme:
        failures.append("README.md is missing env documentation for: " + ", ".join(missing_in_readme))
    if extra_in_production:
        failures.append(
            ".env.production.example contains keys not present in .env.example: "
            + ", ".join(extra_in_production)
        )
    if missing_from_production:
        failures.append(
            ".env.production.example is missing keys present in .env.example: "
            + ", ".join(missing_from_production)
        )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Config contract check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
