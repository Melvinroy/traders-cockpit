"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent } from "react";

import { ActivityLog } from "@/components/ActivityLog";
import { CockpitHeader } from "@/components/CockpitHeader";
import { EntryPanel } from "@/components/EntryPanel";
import { LoginPanel } from "@/components/LoginPanel";
import { OpenPositionsPanel } from "@/components/OpenPositionsPanel";
import { ProfitTakingPanel } from "@/components/ProfitTakingPanel";
import { RecentOrdersPanel } from "@/components/RecentOrdersPanel";
import { RunningPnlPanel } from "@/components/RunningPnlPanel";
import { SetupPanel } from "@/components/SetupPanel";
import { StopProtectionPanel } from "@/components/StopProtectionPanel";
import { ApiError, api } from "@/lib/api";
import { defaultAllocationPcts, defaultStopPcts, entryDirection, normalizeAllocationPcts, normalizeStopPcts } from "@/lib/cockpit-ui";
import { evaluateEntryOrderRules } from "@/lib/entry-order-rules";
import { defaultStopModesFor, normalizeStopDraftSelection, resolveStopPreviewSelection, stopDraftKey, type StopDraftSelection } from "@/lib/stop-preview";
import type { AccountView, AuthUser, EntryOrderDraft, EntrySide, LogEntry, OffHoursMode, OrderView, PositionView, SetupResponse, StopMode, TrancheMode } from "@/lib/types";

const DEFAULT_STOP_MODES: StopMode[] = [
  { mode: "stop", pct: 33.33 },
  { mode: "stop", pct: 66.67 },
  { mode: "stop", pct: 100.0 }
];

const DEFAULT_TRANCHE_MODES: TrancheMode[] = [
  { mode: "limit", allocationPct: 33.33, trail: 2, trailUnit: "$", target: "1R", manualPrice: null },
  { mode: "limit", allocationPct: 33.33, trail: 2, trailUnit: "$", target: "2R", manualPrice: null },
  { mode: "runner", allocationPct: 33.34, trail: 2, trailUnit: "$", target: "3R", manualPrice: null }
];

const DEFAULT_ENTRY_ORDER: EntryOrderDraft = {
  side: "buy",
  orderType: "limit",
  timeInForce: "day",
  orderClass: "simple",
  extendedHours: false,
  limitPrice: null,
  stopPrice: null,
  otoExitSide: "stop_loss",
  takeProfit: null,
  stopLoss: null,
};

const MAX_LOG_ENTRIES = 120;
const SETUP_DEBOUNCE_MS = 450;
const STORAGE_LAYOUT_KEY = "cockpit.layout.v3";
const STORAGE_COLLAPSE_KEY = "cockpit.collapse.v2";

type PanelCollapseState = {
  stopProtection: boolean;
  profitTaking: boolean;
  recentOrders: boolean;
  runningPnl: boolean;
  openPositions: boolean;
  activityLog: boolean;
};

type LayoutState = {
  setupWidth: number;
  logWidth: number;
  centerTopPct: number;
  executionLeftPct: number;
  executionLeftTopPct: number;
  monitorRightTopPct: number;
  rightRailTopPct: number;
};

const DEFAULT_COLLAPSE_STATE: PanelCollapseState = {
  stopProtection: false,
  profitTaking: false,
  recentOrders: false,
  runningPnl: false,
  openPositions: false,
  activityLog: false,
};

const DEFAULT_LAYOUT_STATE: LayoutState = {
  setupWidth: 300,
  logWidth: 280,
  centerTopPct: 28,
  executionLeftPct: 50,
  executionLeftTopPct: 56,
  monitorRightTopPct: 56,
  rightRailTopPct: 46,
};

function readStoredJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    return { ...fallback, ...(JSON.parse(raw) as Partial<T>) };
  } catch {
    return fallback;
  }
}

function sanitizeLayoutState(layout: LayoutState): LayoutState {
  return {
    setupWidth: Math.max(240, Math.min(420, layout.setupWidth)),
    logWidth: Math.max(220, Math.min(420, layout.logWidth)),
    centerTopPct: Math.max(18, Math.min(55, layout.centerTopPct)),
    executionLeftPct: Math.max(30, Math.min(70, layout.executionLeftPct)),
    executionLeftTopPct: Math.max(25, Math.min(75, layout.executionLeftTopPct)),
    monitorRightTopPct: Math.max(25, Math.min(75, layout.monitorRightTopPct)),
    rightRailTopPct: Math.max(25, Math.min(75, layout.rightRailTopPct)),
  };
}

function effectiveStopPrice(
  setup: SetupResponse | null,
  stopRef: "lod" | "atr" | "manual",
  manualStop: number | null,
  side: EntrySide,
  entryPrice: number,
) {
  if (!setup) return 0;
  if (stopRef === "manual") return manualStop ?? 0;
  if (stopRef === "atr") {
    const atrOffset = Number.isFinite(setup.atr14) ? setup.atr14 : 0;
    const baseEntry = entryPrice > 0 ? entryPrice : setup.entry;
    return side === "sell"
      ? Number((baseEntry + atrOffset).toFixed(2))
      : Number((baseEntry - atrOffset).toFixed(2));
  }
  return side === "sell" ? setup.hod : setup.lodStop;
}

function deriveSetupForSelection(
  setup: SetupResponse | null,
  account: AccountView | null,
  stopRef: "lod" | "atr" | "manual",
  manualStop: number | null,
  entryPrice: number,
  side: EntrySide,
) {
  if (!setup) return null;
  const equity = account?.equity ?? setup.accountEquity;
  const buyingPower = account?.buying_power ?? setup.accountBuyingPower;
  const riskPct = account?.risk_pct ?? setup.riskPct;
  const stopPrice = effectiveStopPrice(setup, stopRef, manualStop, side, entryPrice);
  const direction = entryDirection(side);
  const validStop = typeof stopPrice === "number"
    && Number.isFinite(stopPrice)
    && stopPrice > 0
    && direction * (entryPrice - stopPrice) > 0;
  const perShareRisk = validStop ? Number(Math.abs(entryPrice - stopPrice).toFixed(2)) : 0;
  const dollarRisk = Number((equity * (riskPct / 100)).toFixed(2));
  const maxNotionalCap = equity * ((account?.max_position_notional_pct ?? 100) / 100);
  const effectiveNotionalCap = Math.min(buyingPower, maxNotionalCap);
  const shares = validStop && entryPrice > 0
    ? Math.max(0, Math.min(Math.floor(dollarRisk / perShareRisk), Math.floor(effectiveNotionalCap / entryPrice)))
    : 0;

  return {
    ...setup,
    entry: entryPrice,
    stopReferenceDefault: stopRef,
    finalStop: validStop ? stopPrice : 0,
    perShareRisk,
    dollarRisk,
    shares,
    riskPct,
    accountEquity: equity,
    accountBuyingPower: buyingPower,
    entryOrder: {
      ...DEFAULT_ENTRY_ORDER,
      ...(setup.entryOrder ?? {}),
      side,
    },
    r1: perShareRisk > 0 ? Number((entryPrice + direction * perShareRisk).toFixed(2)) : entryPrice,
    r2: perShareRisk > 0 ? Number((entryPrice + direction * perShareRisk * 2).toFixed(2)) : entryPrice,
    r3: perShareRisk > 0 ? Number((entryPrice + direction * perShareRisk * 3).toFixed(2)) : entryPrice
  };
}

function defaultTrancheModesFor(count: number): TrancheMode[] {
  const allocations = defaultAllocationPcts(count);
  return DEFAULT_TRANCHE_MODES.map((mode, index) => ({
    ...mode,
    allocationPct: allocations[index] ?? mode.allocationPct,
  }));
}

function buildEntryOrderDraft(
  current: EntryOrderDraft,
  entryPrice: number,
  protectiveStop: number,
  trancheModes: TrancheMode[],
  side: EntrySide,
): EntryOrderDraft {
  const direction = entryDirection(side);
  const perShareRisk = Number(Math.abs(entryPrice - protectiveStop).toFixed(2));
  const next = {
    ...current,
    side,
    limitPrice: current.orderType === "limit" || current.orderType === "stop_limit" ? (current.limitPrice ?? entryPrice) : null,
    stopPrice: current.orderType === "stop" || current.orderType === "stop_limit" ? (current.stopPrice ?? entryPrice) : null,
  };
  const primaryProfitMode = trancheModes[0];
  const takeProfitLimit = primaryProfitMode
    ? primaryProfitMode.target === "Manual" && primaryProfitMode.manualPrice !== null
      ? primaryProfitMode.manualPrice
      : primaryProfitMode.target === "Manual"
        ? null
      : primaryProfitMode.mode === "runner"
        ? null
        : Number((entryPrice + direction * perShareRisk * { "1R": 1, "2R": 2, "3R": 3 }[primaryProfitMode.target]).toFixed(2))
    : null;
  if (next.orderClass === "bracket") {
    next.takeProfit = { limitPrice: takeProfitLimit };
    next.stopLoss = { stopPrice: protectiveStop, limitPrice: null };
  } else if (next.orderClass === "oto") {
    if (next.otoExitSide === "take_profit") {
      next.takeProfit = { limitPrice: takeProfitLimit };
      next.stopLoss = null;
    } else {
      next.stopLoss = { stopPrice: protectiveStop, limitPrice: null };
      next.takeProfit = null;
    }
  } else {
    next.takeProfit = null;
    next.stopLoss = null;
  }
  if (next.orderClass === "oco") {
    next.takeProfit = { limitPrice: takeProfitLimit };
    next.stopLoss = { stopPrice: protectiveStop, limitPrice: null };
  }
  return next;
}

export function Cockpit() {
  const [flashState, setFlashState] = useState<Record<string, number>>({});
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("");
  const [activeLoadedTicker, setActiveLoadedTicker] = useState("");
  const [setupLoadPending, setSetupLoadPending] = useState(false);
  const [setupLatencyMs, setSetupLatencyMs] = useState<number | null>(null);
  const [account, setAccount] = useState<AccountView | null>(null);
  const [setup, setSetup] = useState<SetupResponse | null>(null);
  const [positions, setPositions] = useState<PositionView[]>([]);
  const [activeSymbol, setActiveSymbol] = useState("");
  const [entryPrice, setEntryPrice] = useState(0);
  const [manualStop, setManualStop] = useState<number | null>(null);
  const [offHoursMode, setOffHoursMode] = useState<OffHoursMode>("queue_for_open");
  const [entryOrder, setEntryOrder] = useState<EntryOrderDraft>(DEFAULT_ENTRY_ORDER);
  const [stopRef, setStopRef] = useState<"lod" | "atr" | "manual">("lod");
  const [stopMode, setStopMode] = useState(3);
  const [stopModes, setStopModes] = useState<StopMode[]>(DEFAULT_STOP_MODES);
  const [trancheCount, setTrancheCount] = useState(3);
  const [trancheModes, setTrancheModes] = useState<TrancheMode[]>(DEFAULT_TRANCHE_MODES);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [recentOrders, setRecentOrders] = useState<OrderView[]>([]);
  const [cancelingBrokerOrderId, setCancelingBrokerOrderId] = useState<string | null>(null);
  const [offHoursModalOpen, setOffHoursModalOpen] = useState(false);
  const [panelCollapse, setPanelCollapse] = useState<PanelCollapseState>(DEFAULT_COLLAPSE_STATE);
  const [layoutState, setLayoutState] = useState<LayoutState>(DEFAULT_LAYOUT_STATE);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const setupDebounceRef = useRef<number | null>(null);
  const setupRequestSeqRef = useRef(0);
  const setupAbortRef = useRef<AbortController | null>(null);
  const wsHasOpenedRef = useRef(false);
  const activeSymbolRef = useRef("");
  const setupLoadedRef = useRef(false);
  const stopModeRef = useRef(3);
  const stopModesRef = useRef<StopMode[]>(DEFAULT_STOP_MODES);
  const stopDraftsRef = useRef<Record<string, StopDraftSelection>>({});
  const trancheCountRef = useRef(3);
  const trancheModesRef = useRef<TrancheMode[]>(DEFAULT_TRANCHE_MODES);
  const dragCleanupRef = useRef<(() => void) | null>(null);

  const activePosition = useMemo(
    () => positions.find((position) => position.symbol === activeSymbol) ?? null,
    [positions, activeSymbol]
  );
  const draftEntrySide = entryOrder.side;
  const effectiveSetup = useMemo(
    () => deriveSetupForSelection(setup, account, stopRef, manualStop, entryPrice || setup?.entry || 0, draftEntrySide),
    [account, draftEntrySide, entryPrice, manualStop, setup, stopRef]
  );
  const protectiveStopPrice = useMemo(
    () => effectiveStopPrice(setup, stopRef, manualStop, draftEntrySide, entryPrice || setup?.entry || 0),
    [draftEntrySide, entryPrice, manualStop, setup, stopRef]
  );
  const effectiveEntryOrder = useMemo(
    () =>
      buildEntryOrderDraft(
        entryOrder,
        entryPrice || effectiveSetup?.entry || 0,
        protectiveStopPrice,
        trancheModes,
        draftEntrySide,
      ),
    [draftEntrySide, effectiveSetup, entryOrder, entryPrice, protectiveStopPrice, trancheModes]
  );
  const attachedSummary = useMemo(
    () => ({
      takeProfit: effectiveEntryOrder.takeProfit?.limitPrice ?? null,
      stopLoss: effectiveEntryOrder.stopLoss?.stopPrice ?? null,
    }),
    [effectiveEntryOrder]
  );
  const entryOrderIssues = useMemo(
    () =>
      evaluateEntryOrderRules({
        order: effectiveEntryOrder,
        sessionState: effectiveSetup?.sessionState ?? setup?.sessionState ?? "closed",
        executionProvider: effectiveSetup?.executionProvider ?? setup?.executionProvider ?? "paper",
      }),
    [effectiveEntryOrder, effectiveSetup?.executionProvider, effectiveSetup?.sessionState, setup?.executionProvider, setup?.sessionState]
  );
  const entryOrderErrors = useMemo(
    () => entryOrderIssues.filter((issue) => issue.severity === "error"),
    [entryOrderIssues]
  );
  const phase = activePosition?.phase ?? (setup ? "setup_loaded" : "idle");
  const livePrice = activePosition?.livePrice ?? effectiveSetup?.last ?? null;
  const delta = livePrice !== null && effectiveSetup ? livePrice - effectiveSetup.entry : 0;
  const deltaPct = livePrice !== null && effectiveSetup ? ((livePrice - effectiveSetup.entry) / effectiveSetup.entry) * 100 : 0;
  const normalizedTicker = ticker.trim().toUpperCase();
  const tickerMatchesActiveSetup = normalizedTicker.length > 0 && normalizedTicker === activeLoadedTicker;
  const actionTickerMismatch = Boolean(setup) && normalizedTicker.length > 0 && !tickerMatchesActiveSetup;
  const actionsDisabled = !effectiveSetup || setupLoadPending || actionTickerMismatch || entryOrderErrors.length > 0;
  const disabledReason = setupLoadPending
    ? `Resolving ${normalizedTicker || activeLoadedTicker || "ticker"}...`
    : actionTickerMismatch
      ? `Wait for ${normalizedTicker} to finish loading before previewing or entering a trade.`
      : null;
  const activeEntrySide = activePosition?.setup?.entryOrder?.side === "sell" ? "sell" : effectiveEntryOrder.side;
  const leftColumnCollapsed = panelCollapse.stopProtection && panelCollapse.profitTaking;
  const rightColumnCollapsed = panelCollapse.recentOrders && panelCollapse.runningPnl;
  const effectiveExecutionLeftPct = leftColumnCollapsed && !rightColumnCollapsed
    ? 18
    : rightColumnCollapsed && !leftColumnCollapsed
      ? 82
      : layoutState.executionLeftPct;
  const effectiveExecutionLeftTopPct = panelCollapse.stopProtection && !panelCollapse.profitTaking
    ? 18
    : panelCollapse.profitTaking && !panelCollapse.stopProtection
      ? 82
      : layoutState.executionLeftTopPct;
  const centerTopRow = `minmax(170px, ${layoutState.centerTopPct}%)`;
  const centerBottomRow = `minmax(240px, ${100 - layoutState.centerTopPct}%)`;
  const effectiveLogWidth = layoutState.logWidth;
  const effectiveMonitorRightTopPct = panelCollapse.recentOrders && !panelCollapse.runningPnl
    ? 18
    : panelCollapse.runningPnl && !panelCollapse.recentOrders
      ? 82
      : layoutState.monitorRightTopPct;
  const effectiveRightRailTopPct = panelCollapse.openPositions && !panelCollapse.activityLog
    ? 18
    : panelCollapse.activityLog && !panelCollapse.openPositions
      ? 82
      : layoutState.rightRailTopPct;
  const executionLeftTopRow = panelCollapse.stopProtection
    ? "42px"
    : `minmax(180px, ${effectiveExecutionLeftTopPct}%)`;
  const executionLeftBottomRow = panelCollapse.profitTaking
    ? "42px"
    : `minmax(140px, ${100 - effectiveExecutionLeftTopPct}%)`;
  const monitorRightTopRow = panelCollapse.recentOrders
    ? "42px"
    : `minmax(180px, ${effectiveMonitorRightTopPct}%)`;
  const monitorRightBottomRow = panelCollapse.runningPnl
    ? "42px"
    : `minmax(140px, ${100 - effectiveMonitorRightTopPct}%)`;
  const rightRailTopRow = panelCollapse.openPositions
    ? "42px"
    : `minmax(180px, ${effectiveRightRailTopPct}%)`;
  const rightRailBottomRow = panelCollapse.activityLog
    ? "42px"
    : `minmax(140px, ${100 - effectiveRightRailTopPct}%)`;

  useEffect(() => {
    setPanelCollapse(readStoredJson(STORAGE_COLLAPSE_KEY, DEFAULT_COLLAPSE_STATE));
    setLayoutState(sanitizeLayoutState(readStoredJson(STORAGE_LAYOUT_KEY, DEFAULT_LAYOUT_STATE)));
  }, []);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_COLLAPSE_KEY, JSON.stringify(panelCollapse));
  }, [panelCollapse]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_LAYOUT_KEY, JSON.stringify(sanitizeLayoutState(layoutState)));
  }, [layoutState]);

  useEffect(() => () => {
    dragCleanupRef.current?.();
  }, []);

  useEffect(() => {
    activeSymbolRef.current = activeSymbol;
  }, [activeSymbol]);

  useEffect(() => {
    setupLoadedRef.current = Boolean(setup);
  }, [setup]);

  useEffect(() => {
    stopModeRef.current = stopMode;
  }, [stopMode]);

  useEffect(() => {
    stopModesRef.current = stopModes;
  }, [stopModes]);

  useEffect(() => {
    trancheCountRef.current = trancheCount;
  }, [trancheCount]);

  useEffect(() => {
    trancheModesRef.current = trancheModes;
  }, [trancheModes]);

  const pulse = useCallback((key: string) => {
    setFlashState((current) => ({ ...current, [key]: Date.now() }));
    window.setTimeout(() => {
      setFlashState((current) => {
        if (current[key] === undefined) return current;
        const next = { ...current };
        delete next[key];
        return next;
      });
    }, 420);
  }, []);

  const handleApiError = useCallback((error: unknown) => {
    if (error instanceof ApiError && error.status === 401) {
      setAuthRequired(true);
      setAuthUser(null);
      setAuthError("Session expired or missing. Sign in to continue.");
      return true;
    }
    setRuntimeError(error instanceof Error ? error.message : "Request failed.");
    return false;
  }, []);

  const subscribePrice = useCallback((symbol: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "subscribe_price", symbol }));
    }
  }, []);

  const applyPositionState = useCallback(
    (position: PositionView) => {
      const nextStopSelection = resolveStopPreviewSelection({
        position,
        localDraft: stopDraftsRef.current[stopDraftKey(position)] ?? null,
        fallback: {
          stopMode: stopModeRef.current || 3,
          stopModes: stopModesRef.current,
        },
      });
      activeSymbolRef.current = position.symbol;
      setupLoadedRef.current = true;
      setActiveSymbol(position.symbol);
      setTicker(position.symbol);
      setActiveLoadedTicker(position.symbol);
      setSetup(position.setup as SetupResponse);
      setEntryPrice(position.setup.entry);
      setStopRef((position.setup.stopReferenceDefault as "lod" | "atr" | "manual") ?? "lod");
      setManualStop(position.setup.stopReferenceDefault === "manual" ? null : position.setup.finalStop);
      setEntryOrder({
        ...DEFAULT_ENTRY_ORDER,
        side: position.setup.entryOrder?.side === "sell" ? "sell" : "buy",
        limitPrice: position.setup.entry,
      });
      setOffHoursMode("queue_for_open");
      const resolvedTrancheCount = position.trancheCount && position.trancheCount > 0
        ? position.trancheCount
        : trancheCountRef.current || 3;
      const nextTrancheModes = position.trancheModes.length
        ? position.trancheModes
        : trancheModesRef.current.slice(0, resolvedTrancheCount);
      stopDraftsRef.current[stopDraftKey(position)] = nextStopSelection;
      setStopMode(nextStopSelection.stopMode);
      setStopModes(nextStopSelection.stopModes);
      setTrancheCount(resolvedTrancheCount);
      setTrancheModes(nextTrancheModes.length ? nextTrancheModes : defaultTrancheModesFor(resolvedTrancheCount));
      subscribePrice(position.symbol);
    },
    [subscribePrice]
  );

  const clearPendingSetupRequest = useCallback(() => {
    if (setupDebounceRef.current !== null) {
      window.clearTimeout(setupDebounceRef.current);
      setupDebounceRef.current = null;
    }
    setupAbortRef.current?.abort();
    setupAbortRef.current = null;
    setSetupLoadPending(false);
  }, []);

  const prependLog = useCallback((tag: string, message: string, symbol?: string | null) => {
    const nextLog: LogEntry = {
      id: Date.now(),
      symbol: symbol ?? null,
      tag,
      message,
      created_at: new Date().toISOString(),
    };
    setLogs((current) => [nextLog, ...current].slice(0, MAX_LOG_ENTRIES));
  }, []);

  const hydrate = useCallback(
    async (options?: { autoSelectFirst?: boolean }) => {
      const autoSelectFirst = options?.autoSelectFirst ?? false;
      let accountView: AccountView;
      let positionRows: PositionView[];
      let logRows: LogEntry[];
      let recentOrderRows: OrderView[];
      try {
        [accountView, positionRows, logRows, recentOrderRows] = await Promise.all([
          api.getAccount(),
          api.getPositions(),
          api.getLogs(),
          api.getRecentOrders(),
        ]);
      } catch (error) {
        if (handleApiError(error)) return false;
        throw error;
      }

      const openPositions = positionRows.filter((position) =>
        ["entry_pending", "trade_entered", "protected", "P1_done", "P2_done", "runner_only"].includes(position.phase)
      );
      setAccount(accountView);
      setPositions(positionRows);
      setLogs(logRows);
      setRecentOrders(recentOrderRows);
      setAuthRequired(false);
      setAuthError(null);
      setRuntimeError(null);

      if (activeSymbolRef.current) {
        const active = openPositions.find((position) => position.symbol === activeSymbolRef.current);
        if (active) {
          applyPositionState(active);
          return;
        }
        activeSymbolRef.current = "";
        setActiveSymbol("");
      }

      if (autoSelectFirst && !activeSymbolRef.current && !setupLoadedRef.current && openPositions[0]) {
        applyPositionState(openPositions[0]);
      }

      return true;
    },
    [applyPositionState, handleApiError]
  );

  const loadSession = useCallback(async () => {
    try {
      const user = await api.me();
      setAuthUser(user);
      setAuthRequired(false);
      setAuthError(null);
      return user;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setAuthUser(null);
        setAuthRequired(true);
        return null;
      }
      throw error;
    }
  }, []);

  const selectPosition = useCallback(
    (symbol: string, source: PositionView[] = positions) => {
      const position = source.find((item) => item.symbol === symbol);
      if (!position) return;
      applyPositionState(position);
    },
    [applyPositionState, positions]
  );

  useEffect(() => {
    void (async () => {
      const user = await loadSession();
      if (user) {
        await hydrate({ autoSelectFirst: true });
      }
    })();
  }, [hydrate, loadSession]);

  useEffect(() => {
    if (authRequired || !authUser) return;
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8010/ws/cockpit";
    let disposed = false;
    let reconnectDelay = 1000;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        reconnectDelay = 1000;
        setRuntimeError(null);
        if (activeSymbolRef.current) {
          ws.send(JSON.stringify({ action: "subscribe_price", symbol: activeSymbolRef.current }));
        }
        if (wsHasOpenedRef.current) {
          void hydrate({ autoSelectFirst: Boolean(activeSymbolRef.current) });
        } else {
          wsHasOpenedRef.current = true;
        }
      };
      ws.onmessage = (event) => {
        const payload = JSON.parse(event.data) as Record<string, unknown>;
        if ((payload.type === "price" || payload.type === "price_update") && typeof payload.symbol === "string") {
          setPositions((current) =>
            current.map((position) =>
              position.symbol === payload.symbol
                ? { ...position, livePrice: Number(payload.last ?? position.livePrice) }
              : position
            )
          );
        }
        if (payload.type === "position_update" && payload.position && typeof payload.symbol === "string") {
          const nextPosition = payload.position as PositionView;
          setPositions((current) => {
            const next = current.some((position) => position.symbol === nextPosition.symbol)
              ? current.map((position) => (position.symbol === nextPosition.symbol ? nextPosition : position))
              : [nextPosition, ...current];
            return next;
          });
          if (activeSymbolRef.current === nextPosition.symbol) {
            applyPositionState(nextPosition);
          }
        }
        if (payload.type === "order_update" && Array.isArray(payload.orders) && typeof payload.symbol === "string") {
          setPositions((current) =>
            current.map((position) =>
              position.symbol === payload.symbol
                ? { ...position, orders: payload.orders as PositionView["orders"] }
                : position
            )
          );
          void api.getRecentOrders().then(setRecentOrders).catch(() => {});
        }
        if (payload.type === "log_update" && payload.log) {
          const nextLog = payload.log as LogEntry;
          setLogs((current) => {
            const deduped = current.filter((entry) => entry.id !== nextLog.id);
            return [nextLog, ...deduped].slice(0, MAX_LOG_ENTRIES);
          });
        }
      };
      ws.onerror = () => {
        ws.close();
      };
      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (disposed) return;
        if (ws.readyState !== WebSocket.OPEN) {
          setRuntimeError("Realtime connection lost. Reconnecting...");
        }
        reconnectTimerRef.current = window.setTimeout(() => {
          reconnectDelay = Math.min(reconnectDelay * 2, 5000);
          connect();
        }, reconnectDelay);
      };
    };

    connect();
    return () => {
      disposed = true;
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [applyPositionState, authRequired, authUser, hydrate]);

  const loadSetup = useCallback(async (symbolOverride?: string) => {
    const nextTicker = (symbolOverride ?? ticker).trim().toUpperCase();
    if (!nextTicker) {
      setRuntimeError("Enter a ticker before loading setup.");
      return;
    }
    clearPendingSetupRequest();
    const requestId = setupRequestSeqRef.current + 1;
    setupRequestSeqRef.current = requestId;
    const controller = new AbortController();
    setupAbortRef.current = controller;
    setSetupLoadPending(true);
    const startedAt = performance.now();
    let nextSetup: SetupResponse;
    try {
      nextSetup = await api.getSetup(nextTicker, controller.signal);
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      if (handleApiError(error)) {
        setSetupLoadPending(false);
        return;
      }
      const message = error instanceof Error ? error.message : "Unable to load setup.";
      setRuntimeError(`${nextTicker}: ${message}`);
      setSetupLoadPending(false);
      return;
    }
    if (setupRequestSeqRef.current !== requestId) {
      return;
    }
    activeSymbolRef.current = "";
    setupLoadedRef.current = true;
    setActiveLoadedTicker(nextTicker);
    setSetup(nextSetup);
    setEntryPrice(nextSetup.entry);
    setStopRef(nextSetup.stopReferenceDefault);
    setManualStop(nextSetup.stopReferenceDefault === "manual" ? null : nextSetup.finalStop);
    setEntryOrder({
      ...DEFAULT_ENTRY_ORDER,
      side: "buy",
      limitPrice: nextSetup.entry,
    });
    setActiveSymbol("");
    setStopMode(3);
    setStopModes(defaultStopModesFor(3));
    setTrancheCount(3);
    setTrancheModes(defaultTrancheModesFor(3));
    setOffHoursMode("queue_for_open");
    subscribePrice(nextTicker);
    setSetupLatencyMs(Math.round(performance.now() - startedAt));
    pulse("load");
    setRuntimeError(null);
    setSetupLoadPending(false);
    setupAbortRef.current = null;
  }, [clearPendingSetupRequest, handleApiError, pulse, subscribePrice, ticker]);

  useEffect(() => {
    if (!authUser || authRequired) return;
    const nextTicker = ticker.trim().toUpperCase();
    if (!nextTicker || nextTicker === activeLoadedTicker) {
      setSetupLoadPending(false);
      return;
    }
    if (!/^[A-Z]{2,6}$/.test(nextTicker)) {
      setSetupLoadPending(false);
      return;
    }
    setSetupLoadPending(true);
    setupDebounceRef.current = window.setTimeout(() => {
      setupDebounceRef.current = null;
      void loadSetup(nextTicker);
    }, SETUP_DEBOUNCE_MS);

    return () => {
      if (setupDebounceRef.current !== null) {
        window.clearTimeout(setupDebounceRef.current);
        setupDebounceRef.current = null;
      }
    };
  }, [activeLoadedTicker, authRequired, authUser, loadSetup, ticker]);

  async function commitRiskPct(nextRiskPct: number) {
    if (!account) return;
    try {
      await api.updateAccount({
        equity: account.equity,
        risk_pct: nextRiskPct,
        mode: account.mode
      });
      const setupSymbol = activeLoadedTicker || ticker;
      if (setupSymbol) {
        const nextSetup = await api.getSetup(setupSymbol);
        setSetup(nextSetup);
        setEntryPrice(nextSetup.entry);
        setStopRef(nextSetup.stopReferenceDefault);
        setManualStop(nextSetup.stopReferenceDefault === "manual" ? null : nextSetup.finalStop);
        setEntryOrder({
          ...DEFAULT_ENTRY_ORDER,
          side: "buy",
          limitPrice: nextSetup.entry,
        });
        setStopModes(defaultStopModesFor(stopMode));
        setTrancheModes((current) => {
          const allocations = normalizeAllocationPcts(
            current.slice(0, trancheCount).map((item) => item.allocationPct),
            0,
            trancheCount
          );
          return current.map((item, index) =>
            index < trancheCount ? { ...item, allocationPct: allocations[index] } : item
          );
        });
      }
      await hydrate({ autoSelectFirst: false });
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function previewTrade() {
    if (!setup || actionsDisabled) return;
    if (stopRef === "manual" && (!manualStop || manualStop <= 0)) {
      setRuntimeError("Enter a valid manual stop price.");
      return;
    }
    try {
      const preview = await api.previewTrade({
        symbol: activeLoadedTicker || ticker,
        entry: entryPrice,
        stopRef,
        stopPrice: protectiveStopPrice,
        riskPct: account?.risk_pct ?? setup.riskPct,
        order: effectiveEntryOrder,
      });
      prependLog(
        "info",
        `Preview: ${preview.symbol} ${effectiveEntryOrder.side.toUpperCase()} ${preview.shares} sh @ ${preview.entry.toFixed(2)} stop ${preview.finalStop.toFixed(2)}`,
        preview.symbol
      );
      pulse("preview");
      setRuntimeError(preview.sizingWarning ?? null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function enterTrade() {
    if (!setup || actionsDisabled) return;
    if (stopRef === "manual" && (!manualStop || manualStop <= 0)) {
      setRuntimeError("Enter a valid manual stop price.");
      return;
    }
    if (setup.sessionState !== "regular_open" && effectiveEntryOrder.orderType === "market") {
      setOffHoursModalOpen(true);
      return;
    }
    await submitEnterTrade(null);
  }

  async function submitEnterTrade(mode: OffHoursMode | null) {
    if (!setup) return;
    try {
      const position = await api.enterTrade({
        symbol: activeLoadedTicker || ticker,
        entry: entryPrice,
        stopRef,
        stopPrice: protectiveStopPrice,
        trancheCount,
        trancheModes: trancheModes.slice(0, trancheCount),
        offHoursMode: setup.sessionState === "regular_open" ? null : mode,
        order: effectiveEntryOrder,
      });
      setPositions((current) => {
        const next = current.some((item) => item.symbol === position.symbol)
          ? current.map((item) => (item.symbol === position.symbol ? position : item))
          : [position, ...current];
        return next;
      });
      applyPositionState(position);
      setStopMode((current) => current || 3);
      setOffHoursModalOpen(false);
      await hydrate({ autoSelectFirst: false });
      applyPositionState(position);
      pulse("enter");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function executeStops() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    try {
      const position = await api.applyStops({ symbol, stopMode, stopModes });
      await hydrate({ autoSelectFirst: false });
      selectPosition(position.symbol);
      pulse("stop");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function executeProfit() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    try {
      const position = await api.executeProfit({ symbol, trancheModes });
      await hydrate({ autoSelectFirst: false });
      selectPosition(position.symbol);
      pulse("profit");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function moveToBe() {
    if (!activeSymbol) return;
    try {
      const position = await api.moveToBe(activeSymbol);
      await hydrate({ autoSelectFirst: false });
      selectPosition(position.symbol);
      pulse("be");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function flatten() {
    if (!activeSymbol) return;
    try {
      const position = await api.flatten(activeSymbol);
      await hydrate({ autoSelectFirst: false });
      if (position.phase === "closed") {
        activeSymbolRef.current = "";
        setActiveSymbol("");
        setActiveLoadedTicker("");
      }
      pulse("flatten");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function clearLogs() {
    try {
      await api.clearLogs();
      await hydrate({ autoSelectFirst: false });
      pulse("clear");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function cancelOrder(brokerOrderId: string) {
    try {
      setCancelingBrokerOrderId(brokerOrderId);
      await api.cancelOrder(brokerOrderId);
      await hydrate({ autoSelectFirst: false });
      prependLog("warn", `Canceled broker order ${brokerOrderId}.`, activeSymbol || activeLoadedTicker || null);
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    } finally {
      setCancelingBrokerOrderId(null);
    }
  }

  function updateCollapse(key: keyof PanelCollapseState) {
    setPanelCollapse((current) => ({ ...current, [key]: !current[key] }));
  }

  function beginDrag(mode: "setup" | "log" | "center" | "execution" | "execution-left" | "monitor-right" | "right-rail", event: ReactMouseEvent<HTMLDivElement>) {
    if (typeof window === "undefined" || window.innerWidth <= 1024) return;
    event.preventDefault();
    dragCleanupRef.current?.();
    const start = { ...layoutState };
    const startX = event.clientX;
    const startY = event.clientY;

    const onMove = (moveEvent: MouseEvent) => {
      setLayoutState((current) => {
        if (mode === "setup") {
          const deltaX = moveEvent.clientX - startX;
          return { ...current, setupWidth: Math.max(240, Math.min(420, start.setupWidth + deltaX)) };
        }
        if (mode === "log") {
          const deltaX = moveEvent.clientX - startX;
          return { ...current, logWidth: Math.max(220, Math.min(420, start.logWidth - deltaX)) };
        }
        if (mode === "center") {
          const host = document.querySelector(".center-stage") as HTMLElement | null;
          const hostHeight = host?.getBoundingClientRect().height ?? window.innerHeight;
          const deltaY = moveEvent.clientY - startY;
          const nextPct = Math.max(18, Math.min(55, start.centerTopPct + (deltaY / Math.max(hostHeight, 1)) * 100));
          return { ...current, centerTopPct: Number(nextPct.toFixed(2)) };
        }
        if (mode === "execution") {
          const deltaX = moveEvent.clientX - startX;
          const nextPct = Math.max(30, Math.min(70, start.executionLeftPct + (deltaX / window.innerWidth) * 100));
          return { ...current, executionLeftPct: Number(nextPct.toFixed(2)) };
        }
        if (mode === "execution-left") {
          const host = document.querySelector(".execution-column-left") as HTMLElement | null;
          const hostHeight = host?.getBoundingClientRect().height ?? window.innerHeight;
          const deltaY = moveEvent.clientY - startY;
          const nextPct = Math.max(25, Math.min(75, start.executionLeftTopPct + (deltaY / Math.max(hostHeight, 1)) * 100));
          return { ...current, executionLeftTopPct: Number(nextPct.toFixed(2)) };
        }
        if (mode === "monitor-right") {
          const host = document.querySelector(".execution-column-right") as HTMLElement | null;
          const hostHeight = host?.getBoundingClientRect().height ?? window.innerHeight;
          const deltaY = moveEvent.clientY - startY;
          const nextPct = Math.max(25, Math.min(75, start.monitorRightTopPct + (deltaY / Math.max(hostHeight, 1)) * 100));
          return { ...current, monitorRightTopPct: Number(nextPct.toFixed(2)) };
        }
        const host = document.querySelector(".right-rail") as HTMLElement | null;
        const hostHeight = host?.getBoundingClientRect().height ?? window.innerHeight;
        const deltaY = moveEvent.clientY - startY;
        const nextPct = Math.max(25, Math.min(75, start.rightRailTopPct + (deltaY / Math.max(hostHeight, 1)) * 100));
        return { ...current, rightRailTopPct: Number(nextPct.toFixed(2)) };
      });
    };

    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      dragCleanupRef.current = null;
    };

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    dragCleanupRef.current = onUp;
  }

  async function submitLogin(payload: { username: string; password: string }) {
    setAuthBusy(true);
    try {
      const user = await api.login(payload);
      setAuthUser(user);
      setAuthRequired(false);
      setAuthError(null);
      await hydrate({ autoSelectFirst: true });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setAuthError("Invalid credentials.");
        return;
      }
      setAuthError(error instanceof Error ? error.message : "Unable to sign in.");
    } finally {
      setAuthBusy(false);
    }
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      setAuthUser(null);
      setAuthRequired(true);
      setAuthError(null);
      setRuntimeError(null);
      setSetupLatencyMs(null);
      wsHasOpenedRef.current = false;
      clearPendingSetupRequest();
      setSetup(null);
      setPositions([]);
      setLogs([]);
      setRecentOrders([]);
      setAccount(null);
      setActiveSymbol("");
      setActiveLoadedTicker("");
      setTicker("");
      setEntryPrice(0);
      setManualStop(null);
      setEntryOrder(DEFAULT_ENTRY_ORDER);
      activeSymbolRef.current = "";
      setupLoadedRef.current = false;
    }
  }

  if (authRequired) {
    return <LoginPanel error={authError} busy={authBusy} onSubmit={submitLogin} />;
  }

  return (
    <main>
      <CockpitHeader
        phase={phase}
        account={account}
        authUser={authUser}
        onLogout={() => void logout()}
      />
      {runtimeError ? <div className="runtime-banner">{runtimeError}</div> : null}
      <div
        className="workspace"
        style={
          {
            "--setup-width": `${layoutState.setupWidth}px`,
            "--log-width": `${effectiveLogWidth}px`,
            "--center-top-row": centerTopRow,
            "--center-bottom-row": centerBottomRow,
            "--execution-left": `${effectiveExecutionLeftPct}%`,
            "--execution-right": `${100 - effectiveExecutionLeftPct}%`,
            "--execution-left-top": `${effectiveExecutionLeftTopPct}%`,
            "--execution-left-bottom": `${100 - effectiveExecutionLeftTopPct}%`,
            "--monitor-right-top": `${effectiveMonitorRightTopPct}%`,
            "--monitor-right-bottom": `${100 - effectiveMonitorRightTopPct}%`,
            "--right-rail-top": `${effectiveRightRailTopPct}%`,
            "--right-rail-bottom": `${100 - effectiveRightRailTopPct}%`,
            "--execution-left-top-row": executionLeftTopRow,
            "--execution-left-bottom-row": executionLeftBottomRow,
            "--monitor-right-top-row": monitorRightTopRow,
            "--monitor-right-bottom-row": monitorRightBottomRow,
            "--right-rail-top-row": rightRailTopRow,
            "--right-rail-bottom-row": rightRailBottomRow,
          } as CSSProperties
        }
      >
        <SetupPanel
          symbol={activeSymbol || activeLoadedTicker}
          setup={effectiveSetup}
          account={account}
          setupLatencyMs={setupLatencyMs}
          onRiskPctCommit={(value) => void commitRiskPct(value)}
        />
        <div className="workspace-splitter workspace-splitter-setup" onMouseDown={(event) => beginDrag("setup", event)} />
        <div className="center-stage">
          <EntryPanel
            ticker={ticker}
            setupLoadPending={setupLoadPending}
            onTickerChange={setTicker}
            onLoad={() => void loadSetup()}
            setup={effectiveSetup}
            activeSymbolLabel={activeSymbol || activeLoadedTicker || normalizedTicker}
            livePrice={livePrice}
            delta={delta}
            deltaPct={deltaPct}
            entryPrice={entryPrice || effectiveSetup?.entry || 0}
            stopRef={stopRef}
            manualStop={manualStop}
            displayStopPrice={protectiveStopPrice || null}
            order={effectiveEntryOrder}
            orderIssues={entryOrderIssues}
            attachedSummary={attachedSummary}
            actionsDisabled={actionsDisabled}
            disabledReason={disabledReason}
            previewFlashing={Boolean(flashState.preview)}
            enterFlashing={Boolean(flashState.enter)}
            onEntryChange={setEntryPrice}
            onStopRefChange={setStopRef}
            onManualStopChange={setManualStop}
            onOrderChange={setEntryOrder}
            onPreview={() => void previewTrade()}
            onEnterTrade={() => void enterTrade()}
          />
          <div className="workspace-splitter workspace-splitter-horizontal workspace-splitter-center" onMouseDown={(event) => beginDrag("center", event)} />
          <div className="execution-row">
            <div className="execution-column execution-column-left">
              <StopProtectionPanel
                setup={effectiveSetup}
                phase={activePosition?.phase ?? null}
                entrySide={activeEntrySide}
                stopMode={stopMode}
                stopModes={stopModes}
                tranches={activePosition?.tranches ?? []}
                orders={activePosition?.orders ?? []}
                executeFlashing={Boolean(flashState.stop)}
                moveToBeFlashing={Boolean(flashState.be)}
                flattenFlashing={Boolean(flashState.flatten)}
                collapsed={panelCollapse.stopProtection}
                onToggleCollapse={() => updateCollapse("stopProtection")}
                onStopModeChange={(value) => {
                  const nextSelection = normalizeStopDraftSelection(value, defaultStopModesFor(value));
                  const draftKey = activePosition ? stopDraftKey(activePosition) : "";
                  if (draftKey) {
                    stopDraftsRef.current[draftKey] = nextSelection;
                  }
                  setStopMode(nextSelection.stopMode);
                  setStopModes(nextSelection.stopModes);
                }}
                onStopModeValueChange={(index, value) => {
                  const currentStopMode = stopModeRef.current || 3;
                  const draftKey = activePosition ? stopDraftKey(activePosition) : "";
                  const currentModes = stopModesRef.current;
                  const next = currentModes.map((item, itemIndex) => (itemIndex === index ? value : item));
                  const updatedModes = value.mode === "be"
                    ? (() => {
                        const nextModes = [...next];
                        for (let itemIndex = 0; itemIndex <= index; itemIndex += 1) {
                          nextModes[itemIndex] = { ...nextModes[itemIndex], mode: "be", pct: 0 };
                        }
                        const remaining = currentStopMode - (index + 1);
                        for (let itemIndex = index + 1; itemIndex < currentStopMode; itemIndex += 1) {
                          nextModes[itemIndex] = {
                            ...nextModes[itemIndex],
                            mode: "stop",
                            pct: Number((((itemIndex - index) / Math.max(1, remaining)) * 100).toFixed(2)),
                          };
                        }
                        return nextModes;
                      })()
                    : normalizeStopPcts(
                        next,
                        currentStopMode,
                        index,
                        Number(value.pct ?? defaultStopPcts(currentStopMode)[index] ?? 100)
                      );
                  const nextSelection = normalizeStopDraftSelection(currentStopMode, updatedModes);
                  if (draftKey) {
                    stopDraftsRef.current[draftKey] = nextSelection;
                  }
                  setStopModes(nextSelection.stopModes);
                }}
                onExecute={() => void executeStops()}
                onMoveToBe={() => void moveToBe()}
                onFlatten={() => void flatten()}
              />
              <div className="workspace-splitter workspace-splitter-horizontal workspace-splitter-execution-left" onMouseDown={(event) => beginDrag("execution-left", event)} />
              <ProfitTakingPanel
                setup={effectiveSetup}
                activePosition={activePosition}
                entrySide={activeEntrySide}
                trancheCount={trancheCount}
                trancheModes={trancheModes}
                executeFlashing={Boolean(flashState.profit)}
                collapsed={panelCollapse.profitTaking}
                onToggleCollapse={() => updateCollapse("profitTaking")}
                onTrancheCountChange={(value) => {
                  setTrancheCount(value);
                  setTrancheModes(defaultTrancheModesFor(value));
                }}
                onTrancheModeChange={(index, value) =>
                  setTrancheModes((current) => {
                    const next = current.map((item, itemIndex) => (itemIndex === index ? value : item));
                    const allocations = normalizeAllocationPcts(
                      next.slice(0, trancheCount).map((item) => item.allocationPct),
                      index,
                      trancheCount
                    );
                    return next.map((item, itemIndex) =>
                      itemIndex < trancheCount ? { ...item, allocationPct: allocations[itemIndex] } : item
                    );
                  })
                }
                onExecute={() => void executeProfit()}
              />
            </div>
            <div className="workspace-splitter workspace-splitter-execution" onMouseDown={(event) => beginDrag("execution", event)} />
            <div className="execution-column execution-column-right">
              <RecentOrdersPanel
                orders={recentOrders}
                activeSymbol={activeSymbol}
                cancelingBrokerOrderId={cancelingBrokerOrderId}
                collapsed={panelCollapse.recentOrders}
                onToggleCollapse={() => updateCollapse("recentOrders")}
                onCancelOrder={(brokerOrderId) => void cancelOrder(brokerOrderId)}
              />
              <div className="workspace-splitter workspace-splitter-horizontal workspace-splitter-monitor-right" onMouseDown={(event) => beginDrag("monitor-right", event)} />
              <RunningPnlPanel
                activePosition={activePosition}
                setup={effectiveSetup}
                collapsed={panelCollapse.runningPnl}
                onToggleCollapse={() => updateCollapse("runningPnl")}
              />
            </div>
          </div>
        </div>
        <div className="workspace-splitter workspace-splitter-log" onMouseDown={(event) => beginDrag("log", event)} />
        <div className="right-rail">
          <OpenPositionsPanel
            positions={positions}
            activeSymbol={activeSymbol}
            collapsed={panelCollapse.openPositions}
            onToggleCollapse={() => updateCollapse("openPositions")}
            onSelectPosition={selectPosition}
          />
          <div className="workspace-splitter workspace-splitter-horizontal workspace-splitter-right-rail" onMouseDown={(event) => beginDrag("right-rail", event)} />
          <ActivityLog
            logs={logs}
            clearFlashing={Boolean(flashState.clear)}
            onClear={() => void clearLogs()}
            collapsed={panelCollapse.activityLog}
            onToggleCollapse={() => updateCollapse("activityLog")}
          />
        </div>
      </div>
      {offHoursModalOpen && effectiveSetup ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setOffHoursModalOpen(false)}>
          <div className="modal-card" role="dialog" aria-modal="true" aria-labelledby="offhoursTitle" onClick={(event) => event.stopPropagation()}>
            <div className="modal-eyebrow">Alpaca Off-Hours Entry</div>
            <h2 id="offhoursTitle" className="modal-title">{activeLoadedTicker || effectiveSetup.symbol}</h2>
            <div className="modal-copy">
              Session is {effectiveSetup.sessionState.replaceAll("_", " ")}. Standard market orders queue for the next regular session.
              Extended-hours submission must be a limit order and will use the current entry price {effectiveSetup.entry.toFixed(2)}.
            </div>
            <div className="modal-choice-grid">
              <button type="button" className={`modal-choice ${offHoursMode === "queue_for_open" ? "active" : ""}`} onClick={() => setOffHoursMode("queue_for_open")}>
                <span className="modal-choice-title">Queue For Open</span>
                <span className="modal-choice-copy">Submit a regular Alpaca day market order to wait for the next regular session.</span>
              </button>
              <button type="button" className={`modal-choice ${offHoursMode === "extended_hours_limit" ? "active" : ""}`} onClick={() => setOffHoursMode("extended_hours_limit")}>
                <span className="modal-choice-title">Submit Extended-Hours Limit</span>
                <span className="modal-choice-copy">Submit a day limit order with extended-hours enabled using the current entry price.</span>
              </button>
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setOffHoursModalOpen(false)}>CANCEL</button>
              <button type="button" className="btn btn-cyan" onClick={() => void submitEnterTrade(offHoursMode)}>CONFIRM</button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
