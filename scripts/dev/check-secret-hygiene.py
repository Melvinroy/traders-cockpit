from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

TRACKED_ENV_FILE_RE = re.compile(r"(^|/)\.env($|\.)")
SAFE_ENV_FILES = {
    ".env.example",
    ".env.personal-paper.example",
    ".env.production.example",
}
TEXT_SUFFIXES = {
    ".env",
    ".example",
    ".ini",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
GENERIC_SECRET_PATTERNS = {
    "GitHub token": re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style secret": re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}
SECRET_ENV_KEYS = {
    "ALPACA_API_KEY_ID",
    "ALPACA_API_SECRET_KEY",
    "MASSIVE_API_KEY",
    "POLYGON_API_KEY",
    "OPS_API_KEY",
    "OPS_ADMIN_API_KEY",
    "OPS_SIGNING_SECRET",
    "LIVE_CONFIRMATION_TOKEN",
    "AUTH_ADMIN_PASSWORD",
    "AUTH_TRADER_PASSWORD",
}


def is_safe_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'").strip('"')
    if not normalized:
        return True
    lowered = normalized.lower()
    return (
        lowered.startswith("change-me")
        or lowered
        in {
            "<db-user>:<db-password>@<db-host>:5432/<db-name>",
            "<redis-host>:6379/0",
            "<redacted>",
            "redacted",
            "***",
        }
        or ("<" in normalized and ">" in normalized)
    )


def tracked_files(repo_root: Path) -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files"], cwd=repo_root, text=True)
    return [repo_root / line.strip() for line in raw.splitlines() if line.strip()]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    failures: list[str] = []

    for path in tracked_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if TRACKED_ENV_FILE_RE.search(rel) and path.name not in SAFE_ENV_FILES:
            failures.append(f"Tracked env file must not be committed: {rel}")
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in SAFE_ENV_FILES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in GENERIC_SECRET_PATTERNS.items():
            if pattern.search(content):
                failures.append(f"{label} pattern found in tracked file: {rel}")

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env_key = key.strip()
            if env_key in SECRET_ENV_KEYS and not is_safe_placeholder(value):
                failures.append(f"{rel} contains non-placeholder value for {env_key}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("Secret hygiene check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
