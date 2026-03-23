from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.cockpit import EntryOrderDraft


@dataclass
class EntryOrderRuleResult:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


VALID_TIF_BY_TYPE = {
    "market": {"day", "gtc", "ioc", "fok", "opg", "cls"},
    "limit": {"day", "gtc", "ioc", "fok", "opg", "cls"},
    "stop": {"day", "gtc"},
    "stop_limit": {"day", "gtc"},
}


def evaluate_entry_order_rules(order: EntryOrderDraft, session_state: str) -> EntryOrderRuleResult:
    result = EntryOrderRuleResult()

    if order.timeInForce not in VALID_TIF_BY_TYPE[order.orderType]:
        result.errors.append(
            f"{order.orderType.upper()} orders do not support {order.timeInForce.upper()} time-in-force."
        )

    if order.orderType in {"limit", "stop_limit"} and (
        order.limitPrice is None or order.limitPrice <= 0
    ):
        result.errors.append("Limit price is required for limit and stop-limit entries.")

    if order.orderType in {"stop", "stop_limit"} and (
        order.stopPrice is None or order.stopPrice <= 0
    ):
        result.errors.append("Stop trigger price is required for stop and stop-limit entries.")

    if order.extendedHours:
        if order.orderType != "limit" or order.timeInForce not in {"day", "gtc"}:
            result.errors.append("Extended-hours entries must be LIMIT with DAY or GTC.")
        if order.orderClass != "simple":
            result.errors.append("Extended-hours is only available for simple limit entries.")

    if order.orderClass == "oco":
        result.errors.append(
            "OCO is an exit-only Alpaca order class and cannot be used for a new entry."
        )

    if order.orderClass == "bracket":
        if not order.takeProfit or order.takeProfit.limitPrice is None:
            result.errors.append("Bracket orders require a take-profit limit price.")
        if not order.stopLoss or order.stopLoss.stopPrice is None:
            result.errors.append("Bracket orders require a stop-loss stop price.")

    if order.orderClass == "oto":
        if order.otoExitSide == "take_profit":
            if not order.takeProfit or order.takeProfit.limitPrice is None:
                result.errors.append("OTO take-profit orders require a take-profit limit price.")
        elif not order.stopLoss or order.stopLoss.stopPrice is None:
            result.errors.append("OTO stop-loss orders require a stop-loss stop price.")

    if order.orderClass in {"bracket", "oto"} and order.timeInForce not in {"day", "gtc"}:
        result.errors.append("Attached exit orders require DAY or GTC time-in-force.")

    if (
        session_state != "regular_open"
        and order.orderType == "market"
        and order.timeInForce in {"opg", "cls"}
    ):
        result.errors.append(
            "Auction-only market orders are unavailable outside the regular session."
        )

    if (
        session_state != "regular_open"
        and order.orderType == "market"
        and order.timeInForce in {"day", "gtc"}
    ):
        result.notes.append(
            "Market orders outside the regular session require off-hours confirmation."
        )

    return result
