import type { OrderView, PositionView, SetupResponse, StopMode, Tranche, TrancheMode } from "@/lib/types";

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

export function splitShares(total: number, count: number): number[] {
  if (count <= 1) return [total];
  if (count === 2) {
    const first = Math.floor(total / 2);
    return [first, total - first];
  }
  const first = Math.floor(total * 0.33);
  const second = Math.floor(total * 0.33);
  return [first, second, total - first - second];
}

export function targetPrice(setup: SetupResponse, mode: TrancheMode): number | null {
  if (mode.mode === "runner") return null;
  if (mode.target === "Manual") return mode.manualPrice;
  const multiplier = { "1R": 1, "2R": 2, "3R": 3 }[mode.target];
  return Number((setup.entry + setup.perShareRisk * multiplier).toFixed(2));
}

export function trailingStop(livePrice: number, mode: TrancheMode): number {
  return mode.trailUnit === "$"
    ? Number((livePrice - mode.trail).toFixed(2))
    : Number((livePrice * (1 - mode.trail / 100)).toFixed(2));
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
  orders: OrderView[]
): Array<{ label: string; qty: number; price: number; pct: number; mode: StopMode["mode"]; status: string; coveredTranches: string[] }> {
  if (!setup) return [];
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
    : splitShares(setup.shares, modeCount).map((qty, index) => ({
        id: `T${index + 1}`,
        qty,
        stop: setup.finalStop,
        status: "active" as const,
        mode: "limit" as const,
        trail: 2,
        trailUnit: "$" as const,
        label: `Tranche ${index + 1}`
      }));
  const range = setup.entry - setup.finalStop;
  return stopGroups(previewTranches, modeCount).map((group, index) => {
    const config = stopModes[index] ?? { mode: "stop", pct: null };
    const autoPct = index === modeCount - 1
      ? 100 - Math.floor(100 / modeCount) * index
      : Math.floor(100 / modeCount);
    const pct = config.mode === "be" ? 0 : (config.pct ?? autoPct);
    const price = config.mode === "be" ? setup.entry : Number((setup.entry - range * pct / 100).toFixed(2));
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
