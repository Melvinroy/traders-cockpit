import { defaultStopPcts } from "@/lib/cockpit-ui";
import type { OrderView, PositionView, StopMode } from "@/lib/types";

export type StopDraftSelection = {
  stopMode: number;
  stopModes: StopMode[];
};

type StopPreviewPosition = Pick<PositionView, "stopMode" | "stopModes" | "orders" | "rootOrderId" | "symbol">;

function clampStopMode(value: number): number {
  return value === 1 || value === 2 || value === 3 ? value : 3;
}

export function defaultStopModesFor(stopMode: number): StopMode[] {
  const resolvedStopMode = clampStopMode(stopMode);
  const defaults = defaultStopPcts(resolvedStopMode);
  return Array.from({ length: resolvedStopMode }, (_, index) => ({
    mode: "stop" as const,
    pct: defaults[index] ?? 100,
  }));
}

export function normalizeStopDraftSelection(stopMode: number, stopModes: StopMode[]): StopDraftSelection {
  const resolvedStopMode = clampStopMode(stopMode);
  const defaults = defaultStopModesFor(resolvedStopMode);
  return {
    stopMode: resolvedStopMode,
    stopModes: defaults.map((fallbackMode, index) => {
      const next = stopModes[index];
      if (!next) return fallbackMode;
      if (next.mode === "be") {
        return { mode: "be", pct: 0 };
      }
      return {
        mode: "stop",
        pct: next.pct ?? fallbackMode.pct,
      };
    }),
  };
}

export function hasCommittedStopOrders(position: Pick<StopPreviewPosition, "stopMode" | "orders">): boolean {
  if (position.stopMode > 0) return true;
  return position.orders.some(
    (order: OrderView) => order.type === "STOP" && order.tranche.startsWith("S") && order.status !== "CANCELED",
  );
}

export function stopDraftKey(position: Pick<StopPreviewPosition, "rootOrderId" | "symbol">): string {
  return position.rootOrderId || position.symbol;
}

export function resolveStopPreviewSelection(args: {
  position: StopPreviewPosition;
  localDraft?: StopDraftSelection | null;
  fallback?: StopDraftSelection | null;
}): StopDraftSelection {
  const { position, localDraft = null, fallback = null } = args;
  if (hasCommittedStopOrders(position)) {
    const committedMode = clampStopMode(position.stopMode || position.stopModes.length || 3);
    return normalizeStopDraftSelection(committedMode, position.stopModes);
  }
  if (localDraft) {
    return normalizeStopDraftSelection(localDraft.stopMode, localDraft.stopModes);
  }
  if (fallback) {
    return normalizeStopDraftSelection(fallback.stopMode, fallback.stopModes);
  }
  return normalizeStopDraftSelection(3, defaultStopModesFor(3));
}
