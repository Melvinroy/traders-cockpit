import type { EntrySide, OrderView, PositionView, SetupResponse, StopMode, Tranche, TrancheMode } from "@/lib/types";

export const ACTIVE_PHASES = ["entry_pending", "trade_entered", "protected", "P1_done", "P2_done", "runner_only"] as const;

const PHASE_LABELS: Record<string, string> = {
  idle: "IDLE",
  setup_loaded: "SETUP LOADED",
  entry_pending: "ENTRY SUBMITTED",
  trade_entered: "TRADE ENTERED",
  protected: "PROTECTED",
  P1_done: "P1 DONE",
  P2_done: "P2 DONE",
  runner_only: "RUNNER ONLY",
  closed: "CLOSED"
};

export function isActivePhase(phase: string): boolean {
  return ACTIVE_PHASES.includes(phase as (typeof ACTIVE_PHASES)[number]);
}

export function fp(value: number | null | undefined): string {
  return Number.isFinite(value) ? Number(value).toFixed(2) : "\u2014";
}

export function f2(value: number | null | undefined): string {
  return Number.isFinite(value) ? `$${Number(value).toFixed(2)}` : "\u2014";
}

export function signedMoney(value: number): string {
  return `${value >= 0 ? "+" : "-"}${f2(Math.abs(value))}`;
}

export function formatLogTime(value: string): string {
  return new Date(value).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
}

export function formatQuoteTimestamp(value: string | null | undefined): string {
  if (!value) return "\u2014";
  return new Date(value).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

export function sessionStateLabel(value: string | null | undefined): string {
  return value ? value.replaceAll("_", " ") : "\u2014";
}

export function phaseLabel(phase: string): string {
  return PHASE_LABELS[phase] ?? phase.replaceAll("_", " ").toUpperCase();
}

export function entrySideFromSetup(setup: SetupResponse | null | undefined): EntrySide {
  return setup?.entryOrder?.side === "sell" ? "sell" : "buy";
}

export function entryDirection(side: EntrySide): 1 | -1 {
  return side === "sell" ? -1 : 1;
}

export function defaultAllocationPcts(count: number): number[] {
  if (count <= 1) return [100];
  const even = Math.floor((100 / count) * 100) / 100;
  const allocations = Array.from({ length: count }, () => even);
  allocations[count - 1] = Number((100 - even * (count - 1)).toFixed(2));
  return allocations;
}

export function normalizeAllocationPcts(
  values: Array<number | null | undefined>,
  changedIndex: number,
  count: number
): number[] {
  const next = defaultAllocationPcts(count);
  const clampedChanged = Math.max(0, Math.min(100, Number(values[changedIndex] ?? next[changedIndex])));
  next[changedIndex] = Number(clampedChanged.toFixed(2));
  const otherIndexes = Array.from({ length: count }, (_, index) => index).filter((index) => index !== changedIndex);
  if (otherIndexes.length === 0) return [100];
  const remaining = Math.max(0, Number((100 - next[changedIndex]).toFixed(2)));
  const originalOtherTotal = otherIndexes.reduce((sum, index) => sum + Math.max(0, Number(values[index] ?? next[index])), 0);
  if (originalOtherTotal <= 0) {
    const even = Number((remaining / otherIndexes.length).toFixed(2));
    otherIndexes.forEach((index, itemIndex) => {
      next[index] = itemIndex === otherIndexes.length - 1
        ? Number((remaining - even * (otherIndexes.length - 1)).toFixed(2))
        : even;
    });
  } else {
    let assigned = 0;
    otherIndexes.forEach((index, itemIndex) => {
      if (itemIndex === otherIndexes.length - 1) {
        next[index] = Number((remaining - assigned).toFixed(2));
        return;
      }
      const proportional = Number((((Math.max(0, Number(values[index] ?? 0)) / originalOtherTotal) * remaining)).toFixed(2));
      next[index] = proportional;
      assigned = Number((assigned + proportional).toFixed(2));
    });
  }
  return next;
}

export function splitShares(total: number, count: number, allocationPcts?: Array<number | null | undefined>): number[] {
  if (count <= 1) return [total];
  if (!total) return Array.from({ length: count }, () => 0);
  const allocations = allocationPcts && allocationPcts.length >= count
    ? allocationPcts.slice(0, count).map((value, index) => value ?? defaultAllocationPcts(count)[index])
    : defaultAllocationPcts(count);
  const raw = allocations.map((allocation) => (total * allocation) / 100);
  const assigned = raw.map((value) => Math.floor(value));
  let remaining = total - assigned.reduce((sum, value) => sum + value, 0);
  const remainders = raw
    .map((value, index) => ({ index, remainder: value - assigned[index] }))
    .sort((left, right) => right.remainder - left.remainder || left.index - right.index);
  for (const item of remainders) {
    if (remaining <= 0) break;
    assigned[item.index] += 1;
    remaining -= 1;
  }
  return assigned;
}

export function defaultStopPcts(stopMode: number): number[] {
  if (stopMode <= 1) return [100];
  return Array.from({ length: stopMode }, (_, index) =>
    Number((((index + 1) / stopMode) * 100).toFixed(2))
  );
}

export function normalizeStopPcts(
  stopModes: StopMode[],
  stopMode: number,
  changedIndex: number,
  nextPct: number
): StopMode[] {
  const current = stopModes.slice(0, stopMode).map((mode, index) => ({
    mode: mode.mode,
    pct: mode.mode === "be" ? 0 : mode.pct ?? defaultStopPcts(stopMode)[index],
  }));
  const normalizedDefaults = defaultStopPcts(stopMode);
  const lowerAnchor = changedIndex === 0 ? 0 : (current[changedIndex - 1]?.mode === "be" ? 0 : Number(current[changedIndex - 1]?.pct ?? normalizedDefaults[changedIndex - 1]));
  const upperAnchor = changedIndex === stopMode - 1 ? 100 : (current[changedIndex + 1]?.mode === "be" ? normalizedDefaults[changedIndex + 1] : Number(current[changedIndex + 1]?.pct ?? normalizedDefaults[changedIndex + 1]));
  const clamped = Math.max(lowerAnchor, Math.min(upperAnchor, nextPct));
  current[changedIndex] = { ...current[changedIndex], pct: Number(clamped.toFixed(2)) };

  let previous = 0;
  for (let index = 0; index < stopMode; index += 1) {
    if (current[index].mode === "be") {
      current[index].pct = 0;
      continue;
    }
    if (index < changedIndex) {
      const slots = changedIndex - index + 1;
      current[index].pct = Number((previous + (clamped - previous) / slots).toFixed(2));
    } else if (index > changedIndex) {
      const nextSlots = stopMode - changedIndex;
      current[index].pct = Number((clamped + ((100 - clamped) * (index - changedIndex)) / nextSlots).toFixed(2));
    }
    previous = Number(current[index].pct ?? 0);
  }

  return stopModes.map((mode, index) => {
    if (index >= stopMode) return mode;
    return current[index];
  });
}

export function targetPrice(
  setup: SetupResponse,
  mode: TrancheMode,
  side: EntrySide = entrySideFromSetup(setup),
): number | null {
  if (mode.mode === "runner") return null;
  if (mode.target === "Manual") return mode.manualPrice;
  const multiplier = { "1R": 1, "2R": 2, "3R": 3 }[mode.target];
  return Number((setup.entry + entryDirection(side) * setup.perShareRisk * multiplier).toFixed(2));
}

export function trailingStop(livePrice: number, mode: TrancheMode, side: EntrySide = "buy"): number {
  const direction = entryDirection(side);
  return mode.trailUnit === "$"
    ? Number((livePrice - direction * mode.trail).toFixed(2))
    : Number((livePrice * (1 - direction * (mode.trail / 100))).toFixed(2));
}

export function stopGroups(tranches: Tranche[], stopMode: number): Tranche[][] {
  const active = tranches.filter((tranche) => tranche.status === "active");
  if (stopMode <= 1) return [active];
  if (stopMode === 2) {
    const midpoint = Math.max(1, Math.floor(active.length / 2));
    return [active.slice(0, midpoint), active.slice(midpoint)];
  }
  return active.map((tranche) => [tranche]);
}

function allTrancheStopGroups(tranches: Tranche[], stopMode: number): Tranche[][] {
  if (stopMode <= 1) return [tranches];
  if (stopMode === 2) {
    const midpoint = Math.max(1, Math.floor(tranches.length / 2));
    return [tranches.slice(0, midpoint), tranches.slice(midpoint)];
  }
  return tranches.map((tranche) => [tranche]);
}

export function stopPlanRows(
  setup: SetupResponse | null,
  tranches: Tranche[],
  stopMode: number,
  stopModes: StopMode[],
  orders: OrderView[],
  side: EntrySide = entrySideFromSetup(setup),
): Array<{ label: string; qty: number; price: number; pct: number; mode: StopMode["mode"]; status: string; coveredTranches: string[] }> {
  if (!setup) return [];
  const direction = entryDirection(side);
  const modeCount = stopMode || 3;
  const stopOrders = orders
    .filter((order) => order.type === "STOP")
    .sort((left, right) => Number(left.tranche.replace("S", "")) - Number(right.tranche.replace("S", "")));
  if (stopOrders.length > 0 && stopOrders.length === modeCount) {
    const coverageGroups = allTrancheStopGroups(tranches, modeCount);
    return stopOrders.map((order, index) => {
      const config = stopModes[index] ?? { mode: "stop", pct: null };
      const autoPct = index === stopOrders.length - 1
        ? 100 - Math.floor(100 / stopOrders.length) * index
        : Math.floor(100 / stopOrders.length);
      return {
        label: order.tranche,
        qty: order.origQty || order.qty,
        price: order.price,
        pct: config.mode === "be" ? 0 : (config.pct ?? autoPct),
        mode: config.mode,
        status: order.status,
        coveredTranches: order.coveredTranches.length
          ? order.coveredTranches
          : (coverageGroups[index] ?? []).map((tranche) => tranche.id)
      };
    });
  }
  const previewTranches = tranches.length
    ? tranches
    : splitShares(
        setup.shares,
        modeCount,
        defaultAllocationPcts(modeCount)
      ).map((qty, index) => ({
        id: `T${index + 1}`,
        qty,
        stop: setup.finalStop,
        status: "active" as const,
        mode: "limit" as const,
        trail: 2,
        trailUnit: "$" as const,
        label: `Tranche ${index + 1}`
      }));
  const range = Math.abs(setup.entry - setup.finalStop);
  return stopGroups(previewTranches, modeCount).map((group, index) => {
    const config = stopModes[index] ?? { mode: "stop", pct: null };
    const autoPct = index === modeCount - 1
      ? 100 - Math.floor(100 / modeCount) * index
      : Math.floor(100 / modeCount);
    const pct = config.mode === "be" ? 0 : (config.pct ?? autoPct);
    const price = config.mode === "be"
      ? setup.entry
      : Number((setup.entry - direction * range * pct / 100).toFixed(2));
    const qty = group.reduce((sum, tranche) => sum + tranche.qty, 0);
    const activeOrder = orders.find(
      (order) =>
        order.type === "STOP" &&
        order.status !== "CANCELED" &&
        group.some((tranche) => order.coveredTranches.includes(tranche.id))
    );
    return {
      label: `S${index + 1}`,
      qty,
      price,
      pct,
      mode: config.mode,
      status: activeOrder ? activeOrder.status : "PREVIEW",
      coveredTranches: group.map((tranche) => tranche.id)
    };
  });
}

export function activeShares(position: PositionView): number {
  return position.tranches
    .filter((tranche) => tranche.status === "active")
    .reduce((sum, tranche) => sum + tranche.qty, 0);
}

export function soldShares(position: PositionView): number {
  return position.tranches
    .filter((tranche) => tranche.status === "sold")
    .reduce((sum, tranche) => sum + tranche.qty, 0);
}

export type RunningPnlSummary = {
  totalShares: number;
  closedShares: number;
  remainingShares: number;
  realizedPnl: number;
  unrealizedPnl: number;
  openRisk: number;
  filledLegs: Array<{
    label: string;
    qty: number;
    exitPrice: number | null;
    pnl: number;
    filledAt: string | null;
  }>;
};

export function runningPnlSummary(position: PositionView | null, setup: SetupResponse | null): RunningPnlSummary | null {
  if (!position || !setup || position.phase === "entry_pending") return null;
  const entry = setup.entry;
  const side = entrySideFromSetup(setup);
  const direction = entryDirection(side);
  const totalShares = position.tranches.reduce((sum, tranche) => sum + tranche.qty, 0);
  const activeTranches = position.tranches.filter((tranche) => tranche.status === "active");
  const closedTranches = position.tranches.filter((tranche) => tranche.status === "sold");
  const remainingShares = activeTranches.reduce((sum, tranche) => sum + tranche.qty, 0);
  const closedShares = closedTranches.reduce((sum, tranche) => sum + tranche.qty, 0);

  const filledLegs = closedTranches.map((tranche) => {
    const fillOrder = [...position.orders]
      .filter((order) => order.status === "FILLED" && (order.tranche === tranche.id || order.coveredTranches.includes(tranche.id)))
      .sort((left, right) => {
        const leftTime = left.filledAt ?? left.updatedAt ?? left.createdAt ?? "";
        const rightTime = right.filledAt ?? right.updatedAt ?? right.createdAt ?? "";
        return rightTime.localeCompare(leftTime);
      })[0];
    const exitPrice = tranche.exitPrice ?? fillOrder?.fillPrice ?? tranche.target ?? null;
    const pnl = exitPrice !== null
      ? Number((((exitPrice - entry) * direction) * tranche.qty).toFixed(2))
      : 0;
    const exitOrderType = tranche.exitOrderType ?? fillOrder?.type ?? null;
    const label = exitOrderType === "STOP"
      ? `Stop hit · ${tranche.id}`
      : exitOrderType === "TRAIL"
        ? `Runner exit · ${tranche.id}`
        : `${tranche.id} filled`;
    return {
      label,
      qty: tranche.qty,
      exitPrice,
      pnl,
      filledAt: tranche.exitFilledAt ?? fillOrder?.filledAt ?? fillOrder?.updatedAt ?? fillOrder?.createdAt ?? null,
    };
  });

  const realizedPnl = Number(filledLegs.reduce((sum, leg) => sum + leg.pnl, 0).toFixed(2));
  const unrealizedPnl = Number((((position.livePrice - entry) * direction) * remainingShares).toFixed(2));
  const openRisk = Number(
    activeTranches.reduce(
      (sum, tranche) => sum + Math.max(0, ((entry - tranche.stop) * direction) * tranche.qty),
      0,
    ).toFixed(2)
  );

  return {
    totalShares,
    closedShares,
    remainingShares,
    realizedPnl,
    unrealizedPnl,
    openRisk,
    filledLegs,
  };
}
