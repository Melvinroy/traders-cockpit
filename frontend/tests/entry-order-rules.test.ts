import { describe, expect, it } from "vitest";

import { evaluateEntryOrderRules } from "@/lib/entry-order-rules";
import type { EntryOrderDraft, SetupResponse } from "@/lib/types";

const DEFAULT_ORDER: EntryOrderDraft = {
  side: "buy",
  orderType: "limit",
  timeInForce: "day",
  orderClass: "simple",
  extendedHours: false,
  limitPrice: 100,
  stopPrice: null,
  otoExitSide: "stop_loss",
  takeProfit: null,
  stopLoss: null,
};

function issuesFor(order: Partial<EntryOrderDraft>, sessionState: SetupResponse["sessionState"] = "regular_open") {
  return evaluateEntryOrderRules({
    order: { ...DEFAULT_ORDER, ...order },
    sessionState,
    executionProvider: "paper",
  });
}

describe("evaluateEntryOrderRules", () => {
  it("flags stop orders with unsupported IOC time-in-force", () => {
    const issues = issuesFor({ orderType: "stop", timeInForce: "ioc", stopPrice: 101 });
    expect(issues.some((issue) => issue.message.includes("STOP orders do not support IOC"))).toBe(true);
  });

  it("flags OCO as an entry-time error", () => {
    const issues = issuesFor({ orderClass: "oco" });
    expect(issues.some((issue) => issue.message.includes("exit-only Alpaca order class"))).toBe(true);
  });

  it("flags bracket orders with unsupported FOK time-in-force", () => {
    const issues = issuesFor({
      orderType: "market",
      timeInForce: "fok",
      orderClass: "bracket",
      takeProfit: { limitPrice: 101 },
      stopLoss: { stopPrice: 99, limitPrice: null },
    });
    expect(issues.some((issue) => issue.message.includes("Attached exit orders require DAY or GTC"))).toBe(true);
  });

  it("emits an off-hours note for market day orders outside the regular session", () => {
    const issues = issuesFor({ orderType: "market", timeInForce: "day", limitPrice: null }, "closed");
    expect(issues.some((issue) => issue.severity === "note" && issue.message.includes("off-hours confirmation"))).toBe(true);
  });
});
