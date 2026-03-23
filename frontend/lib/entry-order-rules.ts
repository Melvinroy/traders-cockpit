import type { EntryOrderDraft, SetupResponse } from "@/lib/types";

export type EntryOrderIssueField =
  | "orderType"
  | "timeInForce"
  | "orderClass"
  | "limitPrice"
  | "stopPrice"
  | "extendedHours"
  | "session";

export type EntryOrderIssue = {
  field: EntryOrderIssueField;
  severity: "error" | "note";
  message: string;
};

const VALID_TIF_BY_TYPE = {
  market: new Set(["day", "gtc", "ioc", "fok", "opg", "cls"]),
  limit: new Set(["day", "gtc", "ioc", "fok", "opg", "cls"]),
  stop: new Set(["day", "gtc"]),
  stop_limit: new Set(["day", "gtc"]),
} as const;

export function evaluateEntryOrderRules(args: {
  order: EntryOrderDraft;
  sessionState?: SetupResponse["sessionState"] | null;
  executionProvider?: string | null;
}): EntryOrderIssue[] {
  const { order, sessionState = "closed" } = args;
  const issues: EntryOrderIssue[] = [];

  if (!VALID_TIF_BY_TYPE[order.orderType].has(order.timeInForce)) {
    issues.push({
      field: "timeInForce",
      severity: "error",
      message: `${order.orderType.toUpperCase()} orders do not support ${order.timeInForce.toUpperCase()} time-in-force.`,
    });
  }

  if ((order.orderType === "limit" || order.orderType === "stop_limit") && (!order.limitPrice || order.limitPrice <= 0)) {
    issues.push({
      field: "limitPrice",
      severity: "error",
      message: "Limit price is required for limit and stop-limit entries.",
    });
  }

  if ((order.orderType === "stop" || order.orderType === "stop_limit") && (!order.stopPrice || order.stopPrice <= 0)) {
    issues.push({
      field: "stopPrice",
      severity: "error",
      message: "Stop trigger price is required for stop and stop-limit entries.",
    });
  }

  if (order.extendedHours) {
    if (order.orderType !== "limit" || !["day", "gtc"].includes(order.timeInForce)) {
      issues.push({
        field: "extendedHours",
        severity: "error",
        message: "Extended-hours entries must be LIMIT with DAY or GTC.",
      });
    }
    if (order.orderClass !== "simple") {
      issues.push({
        field: "extendedHours",
        severity: "error",
        message: "Extended-hours is only available for simple limit entries.",
      });
    }
  }

  if (order.orderClass === "oco") {
    issues.push({
      field: "orderClass",
      severity: "error",
      message: "OCO is an exit-only Alpaca order class and cannot be used for a new entry.",
    });
  }

  if (order.orderClass === "bracket") {
    if (!order.takeProfit || order.takeProfit.limitPrice === null) {
      issues.push({
        field: "orderClass",
        severity: "error",
        message: "Bracket orders require a take-profit limit price.",
      });
    }
    if (!order.stopLoss || order.stopLoss.stopPrice === null) {
      issues.push({
        field: "orderClass",
        severity: "error",
        message: "Bracket orders require a stop-loss stop price.",
      });
    }
  }

  if (order.orderClass === "oto") {
    if (order.otoExitSide === "take_profit") {
      if (!order.takeProfit || order.takeProfit.limitPrice === null) {
        issues.push({
          field: "orderClass",
          severity: "error",
          message: "OTO take-profit orders require a take-profit limit price.",
        });
      }
    } else if (!order.stopLoss || order.stopLoss.stopPrice === null) {
      issues.push({
        field: "orderClass",
        severity: "error",
        message: "OTO stop-loss orders require a stop-loss stop price.",
      });
    }
  }

  if (["bracket", "oto"].includes(order.orderClass) && !["day", "gtc"].includes(order.timeInForce)) {
    issues.push({
      field: "timeInForce",
      severity: "error",
      message: "Attached exit orders require DAY or GTC time-in-force.",
    });
  }

  if (sessionState !== "regular_open" && order.orderType === "market" && ["opg", "cls"].includes(order.timeInForce)) {
    issues.push({
      field: "session",
      severity: "error",
      message: "Auction-only market orders are unavailable outside the regular session.",
    });
  }

  if (sessionState !== "regular_open" && order.orderType === "market" && ["day", "gtc"].includes(order.timeInForce)) {
    issues.push({
      field: "session",
      severity: "note",
      message: "Market orders outside the regular session require off-hours confirmation.",
    });
  }

  return issues;
}

export function firstEntryOrderIssue(
  issues: EntryOrderIssue[],
  field: EntryOrderIssueField,
  severity: EntryOrderIssue["severity"] = "error",
): string | null {
  return issues.find((issue) => issue.field === field && issue.severity === severity)?.message ?? null;
}
