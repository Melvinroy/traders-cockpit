from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps_auth import require_session
from app.db.session import get_db

GRADE_WEIGHT = {
    "A+ Bullish": 100,
    "A+ Bearish": 100,
    "A Bullish": 86,
    "A Bearish": 86,
    "B Bullish": 66,
    "B Bearish": 66,
    "Sympathy / Continuation": 46,
    "N / Neutral": 38,
    "No Fresh Catalyst": 18,
}


def _direction(grade: str) -> str:
    if "Bullish" in grade:
        return "bullish"
    if "Bearish" in grade:
        return "bearish"
    return "neutral"


def _importance(row: dict[str, Any]) -> int:
    score = GRADE_WEIGHT.get(str(row.get("catalyst_quality_direction") or ""), 35)
    if row.get("source_confidence") == "High":
        score += 4
    elif row.get("source_confidence") == "Low":
        score -= 8
    if row.get("direct_sympathy_sector_move") == "Direct":
        score += 4
    if row.get("action_priority") == "High-Conviction Watch":
        score += 4
    elif row.get("action_priority") == "Short Watch":
        score += 2
    freshness = str(row.get("freshness_catalyst_age") or "").lower()
    if "same-day" in freshness or "same day" in freshness:
        score += 2
    return max(10, min(100, score))


def _row_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    if isinstance(payload.get("trading_date_checked"), date):
        payload["trading_date_checked"] = payload["trading_date_checked"].isoformat()
    if payload.get("generated_at_sgt") is not None:
        payload["generated_at_sgt"] = payload["generated_at_sgt"].isoformat()
    payload["direction"] = _direction(str(payload.get("catalyst_quality_direction") or ""))
    payload["importance_score"] = _importance(payload)
    return payload


def build_router() -> APIRouter:
    router = APIRouter(
        prefix="/api/catalysts",
        tags=["catalysts"],
        dependencies=[Depends(require_session)],
    )

    @router.get("")
    def get_catalysts(
        days: int = Query(default=1, ge=1, le=5),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        try:
            as_of = db.execute(
                text("select max(trading_date_checked) from catalyst_dashboard_rows")
            ).scalar_one_or_none()
            if as_of is None:
                return {
                    "days": days,
                    "as_of_date": None,
                    "rows": [],
                    "reports": [],
                    "status": "empty",
                }

            params = {"as_of": as_of, "days": days}
            rows = db.execute(
                text(
                    """
                    with windowed as (
                        select *, count(*) over (partition by ticker) as appearances
                        from catalyst_dashboard_rows
                        where trading_date_checked between
                            (cast(:as_of as date) - (:days - 1)) and cast(:as_of as date)
                    ), latest as (
                        select distinct on (ticker) * from windowed
                        order by ticker, trading_date_checked desc, generated_at_sgt desc, row_order asc
                    )
                    select * from latest
                    order by trading_date_checked desc, generated_at_sgt desc, row_order asc
                    """
                ),
                params,
            ).mappings().all()
            reports = db.execute(
                text(
                    """
                    select id::text as report_id, report_type, trading_date_checked,
                           generated_at_sgt, market_summary, themes_summary, best_focus
                    from catalyst_reports
                    where trading_date_checked between
                        (cast(:as_of as date) - (:days - 1)) and cast(:as_of as date)
                    order by generated_at_sgt desc
                    limit 12
                    """
                ),
                params,
            ).mappings().all()

            report_payloads: list[dict[str, Any]] = []
            for report in reports:
                item = dict(report)
                if isinstance(item.get("trading_date_checked"), date):
                    item["trading_date_checked"] = item["trading_date_checked"].isoformat()
                if item.get("generated_at_sgt") is not None:
                    item["generated_at_sgt"] = item["generated_at_sgt"].isoformat()
                report_payloads.append(item)

            return {
                "days": days,
                "as_of_date": as_of.isoformat() if isinstance(as_of, date) else str(as_of),
                "rows": [_row_payload(dict(row)) for row in rows],
                "reports": report_payloads,
                "status": "ok",
            }
        except SQLAlchemyError:
            db.rollback()
            return {
                "days": days,
                "as_of_date": None,
                "rows": [],
                "reports": [],
                "status": "unavailable",
            }

    return router
