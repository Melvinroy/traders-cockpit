import { describe, expect, it } from "vitest";

import { defaultStopModesFor, hasCommittedStopOrders, normalizeStopDraftSelection, resolveStopPreviewSelection } from "@/lib/stop-preview";
import type { OrderView, PositionView } from "@/lib/types";

function makeOrder(overrides: Partial<OrderView>): OrderView {
  return {
    id: "order-1",
    symbol: "MSFT",
    side: "BUY",
    type: "STOP",
    qty: 100,
    origQty: 100,
    filledQty: 0,
    remainingQty: 100,
    price: 380.18,
    status: "PREVIEW",
    tranche: "S1",
    coveredTranches: ["T1"],
    parentId: null,
    brokerOrderId: null,
    cancelable: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    filledAt: null,
    fillPrice: null,
    ...overrides,
  };
}

function makePosition(overrides: Partial<PositionView> = {}): PositionView {
  return {
    symbol: "MSFT",
    phase: "trade_entered",
    livePrice: 381.9,
    setup: {},
    tranches: [],
    orders: [],
    stopModes: defaultStopModesFor(3),
    stopMode: 0,
    trancheModes: [],
    trancheCount: 3,
    rootOrderId: "root-1",
    ...overrides,
  } as PositionView;
}

describe("stop preview draft resolution", () => {
  it("preserves the local draft when no committed stop orders exist", () => {
    const position = makePosition();
    const draft = normalizeStopDraftSelection(1, [{ mode: "stop", pct: 100 }]);

    const resolved = resolveStopPreviewSelection({ position, localDraft: draft });

    expect(resolved.stopMode).toBe(1);
    expect(resolved.stopModes).toHaveLength(1);
    expect(resolved.stopModes[0]?.pct).toBe(100);
  });

  it("prefers committed stop orders over the local preview draft", () => {
    const position = makePosition({
      stopMode: 2,
      stopModes: normalizeStopDraftSelection(2, [
        { mode: "stop", pct: 40 },
        { mode: "stop", pct: 100 },
      ]).stopModes,
      orders: [makeOrder({ status: "ACTIVE" })],
    });
    const staleDraft = normalizeStopDraftSelection(1, [{ mode: "stop", pct: 100 }]);

    const resolved = resolveStopPreviewSelection({ position, localDraft: staleDraft });

    expect(hasCommittedStopOrders(position)).toBe(true);
    expect(resolved.stopMode).toBe(2);
    expect(resolved.stopModes).toHaveLength(2);
    expect(resolved.stopModes[0]?.pct).toBe(40);
  });

  it("falls back to the provided current selection when no local draft exists", () => {
    const position = makePosition();
    const fallback = normalizeStopDraftSelection(2, [
      { mode: "stop", pct: 50 },
      { mode: "stop", pct: 100 },
    ]);

    const resolved = resolveStopPreviewSelection({ position, fallback });

    expect(resolved.stopMode).toBe(2);
    expect(resolved.stopModes).toHaveLength(2);
    expect(resolved.stopModes[1]?.pct).toBe(100);
  });
});
