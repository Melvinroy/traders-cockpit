from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild position projection payloads from the current backend state tables."
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=[],
        help="Optional symbol filter. Repeat to rebuild multiple symbols.",
    )
    return parser.parse_args()


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    sys.path.insert(0, str(backend_dir))

    from app.db.session import SessionLocal
    from app.main import service

    args = parse_args()
    symbols = [symbol.upper() for symbol in args.symbol if symbol.strip()] or None

    with SessionLocal() as db:
        rebuilt = service.rebuild_position_projections(db, symbols=symbols)
        db.commit()

    target = ", ".join(rebuilt) if rebuilt else "(none)"
    print(f"Rebuilt position projections for: {target}")


if __name__ == "__main__":
    main()
