from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import psycopg
from alembic.config import Config
from alembic.script import ScriptDirectory

REQUIRED_TABLES = {
    "account_settings",
    "positions",
    "orders",
    "trade_log",
    "auth_users",
    "auth_sessions",
    "auth_login_attempts",
}


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set for migration smoke.")

    env = os.environ.copy()
    subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=backend_dir,
        check=True,
        env=env,
    )

    alembic_config = Config(str(backend_dir / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_dir / "alembic"))
    expected_head = ScriptDirectory.from_config(alembic_config).get_current_head()

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                select table_name
                from information_schema.tables
                where table_schema = 'public'
                """)
            actual_tables = {row[0] for row in cursor.fetchall()}
            missing_tables = sorted(REQUIRED_TABLES - actual_tables)
            if missing_tables:
                raise RuntimeError(
                    f"Migration smoke missing required tables: {', '.join(missing_tables)}"
                )

            cursor.execute("select version_num from alembic_version")
            actual_head = cursor.fetchone()[0]

    if actual_head != expected_head:
        raise RuntimeError(
            f"Migration smoke head mismatch: database={actual_head} expected={expected_head}"
        )

    print(
        json.dumps(
            {
                "status": "ok",
                "expected_head": expected_head,
                "tables": sorted(REQUIRED_TABLES),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
