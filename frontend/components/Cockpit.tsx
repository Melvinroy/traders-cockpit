"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ActivityLog } from "@/components/ActivityLog";
import { CockpitHeader } from "@/components/CockpitHeader";
import { EntryPanel } from "@/components/EntryPanel";
import { LoginPanel } from "@/components/LoginPanel";
import { ProfitTakingPanel } from "@/components/ProfitTakingPanel";
import { SetupPanel } from "@/components/SetupPanel";
import { StopProtectionPanel } from "@/components/StopProtectionPanel";
import { ApiError, api } from "@/lib/api";
import type { AccountView, AuthUser, LogEntry, PositionView, SetupResponse, StopMode, TrancheMode } from "@/lib/types";

const DEFAULT_STOP_MODES: StopMode[] = [
  { mode: "stop", pct: null },
  { mode: "stop", pct: null },
  { mode: "stop", pct: null }
];

const DEFAULT_TRANCHE_MODES: TrancheMode[] = [
  { mode: "limit", trail: 2, trailUnit: "$", target: "1R", manualPrice: null },
  { mode: "limit", trail: 2, trailUnit: "$", target: "2R", manualPrice: null },
  { mode: "runner", trail: 2, trailUnit: "$", target: "3R", manualPrice: null }
];

export function Cockpit() {
  const [flashState, setFlashState] = useState<Record<string, number>>({});
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [authBusy, setAuthBusy] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [ticker, setTicker] = useState("AAPL");
  const [account, setAccount] = useState<AccountView | null>(null);
  const [setup, setSetup] = useState<SetupResponse | null>(null);
  const [positions, setPositions] = useState<PositionView[]>([]);
  const [activeSymbol, setActiveSymbol] = useState("");
  const [entryPrice, setEntryPrice] = useState(0);
  const [manualStop, setManualStop] = useState(0);
  const [stopRef, setStopRef] = useState<"lod" | "atr" | "manual">("lod");
  const [stopMode, setStopMode] = useState(3);
  const [stopModes, setStopModes] = useState<StopMode[]>(DEFAULT_STOP_MODES);
  const [trancheCount, setTrancheCount] = useState(3);
  const [trancheModes, setTrancheModes] = useState<TrancheMode[]>(DEFAULT_TRANCHE_MODES);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const activeSymbolRef = useRef("");
  const setupLoadedRef = useRef(false);
  const initialAutoloadRef = useRef(false);

  const activePosition = useMemo(
    () => positions.find((position) => position.symbol === activeSymbol) ?? null,
    [positions, activeSymbol]
  );
  const phase = activePosition?.phase ?? (setup ? "setup_loaded" : "idle");
  const livePrice = activePosition?.livePrice ?? setup?.last ?? null;
  const delta = livePrice !== null && setup ? livePrice - setup.entry : 0;
  const deltaPct = livePrice !== null && setup ? ((livePrice - setup.entry) / setup.entry) * 100 : 0;

  useEffect(() => {
    activeSymbolRef.current = activeSymbol;
  }, [activeSymbol]);

  useEffect(() => {
    setupLoadedRef.current = Boolean(setup);
  }, [setup]);

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
      activeSymbolRef.current = position.symbol;
      setupLoadedRef.current = true;
      setActiveSymbol(position.symbol);
      setTicker(position.symbol);
      setSetup(position.setup as SetupResponse);
      setEntryPrice(position.setup.entry);
      setManualStop(position.setup.finalStop);
      setStopMode(position.stopMode || 3);
      setStopModes(position.stopModes.length ? position.stopModes : DEFAULT_STOP_MODES);
      setTrancheCount(position.trancheCount || 3);
      setTrancheModes(position.trancheModes.length ? position.trancheModes : DEFAULT_TRANCHE_MODES);
      subscribePrice(position.symbol);
    },
    [subscribePrice]
  );

  const hydrate = useCallback(
    async (options?: { autoSelectFirst?: boolean }) => {
      const autoSelectFirst = options?.autoSelectFirst ?? false;
      let accountView: AccountView;
      let positionRows: PositionView[];
      let logRows: LogEntry[];
      try {
        [accountView, positionRows, logRows] = await Promise.all([api.getAccount(), api.getPositions(), api.getLogs()]);
      } catch (error) {
        if (handleApiError(error)) return false;
        throw error;
      }

      const openPositions = positionRows.filter((position) =>
        ["trade_entered", "protected", "P1_done", "P2_done", "runner_only"].includes(position.phase)
      );
      setAccount(accountView);
      setPositions(positionRows);
      setLogs(logRows);
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
      const hydrated = await hydrate({ autoSelectFirst: true });
      if (hydrated) {
        await loadSession();
      }
    })();
  }, [hydrate, loadSession]);

  useEffect(() => {
    if (authRequired) return;
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
        void hydrate({ autoSelectFirst: Boolean(activeSymbolRef.current) });
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
        if (payload.type === "position_update" || payload.type === "order_update" || payload.type === "log_update") {
          void hydrate({ autoSelectFirst: Boolean(activeSymbolRef.current) });
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
        setRuntimeError("Realtime connection lost. Reconnecting...");
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
  }, [authRequired, hydrate]);

  const loadSetup = useCallback(async () => {
    let nextSetup: SetupResponse;
    try {
      nextSetup = await api.getSetup(ticker);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
    activeSymbolRef.current = "";
    setupLoadedRef.current = true;
    setSetup(nextSetup);
    setEntryPrice(nextSetup.entry);
    setManualStop(nextSetup.finalStop);
    setActiveSymbol("");
    setStopMode(3);
    setStopModes(DEFAULT_STOP_MODES);
    subscribePrice(ticker);
    await hydrate({ autoSelectFirst: false });
    pulse("load");
    setRuntimeError(null);
  }, [handleApiError, hydrate, pulse, subscribePrice, ticker]);

  useEffect(() => {
    if (initialAutoloadRef.current) return;
    if (!account) return;
    const hasActivePosition = positions.some((position) =>
      ["trade_entered", "protected", "P1_done", "P2_done", "runner_only"].includes(position.phase)
    );
    if (setup || hasActivePosition || activeSymbolRef.current) {
      initialAutoloadRef.current = true;
      return;
    }
    initialAutoloadRef.current = true;
    void loadSetup();
  }, [account, loadSetup, positions, setup]);

  async function commitRiskPct(nextRiskPct: number) {
    if (!account) return;
    try {
      await api.updateAccount({
        equity: account.equity,
        risk_pct: nextRiskPct,
        mode: account.mode
      });
      if (ticker) {
        const nextSetup = await api.getSetup(ticker);
        setSetup(nextSetup);
        setEntryPrice(nextSetup.entry);
        setManualStop(nextSetup.finalStop);
      }
      await hydrate({ autoSelectFirst: false });
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function previewTrade() {
    if (!setup) return;
    try {
      await api.previewTrade({
        symbol: ticker,
        entry: entryPrice,
        stopRef,
        stopPrice: stopRef === "manual" ? manualStop : setup.finalStop,
        riskPct: account?.risk_pct ?? setup.riskPct
      });
      await hydrate({ autoSelectFirst: false });
      pulse("preview");
      setRuntimeError(null);
    } catch (error) {
      if (handleApiError(error)) return;
      throw error;
    }
  }

  async function enterTrade() {
    if (!setup) return;
    try {
      const position = await api.enterTrade({
        symbol: ticker,
        entry: entryPrice,
        stopRef,
        stopPrice: stopRef === "manual" ? manualStop : setup.finalStop,
        trancheCount,
        trancheModes
      });
      setStopMode((current) => current || 3);
      await hydrate({ autoSelectFirst: false });
      selectPosition(position.symbol, [position, ...positions]);
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
      setSetup(null);
      setPositions([]);
      setLogs([]);
      setAccount(null);
      setActiveSymbol("");
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
        ticker={ticker}
        onTickerChange={setTicker}
        onLoad={() => void loadSetup()}
        onReset={() => {
          activeSymbolRef.current = "";
          setupLoadedRef.current = false;
          setSetup(null);
          setActiveSymbol("");
          setTicker("");
          setEntryPrice(0);
          setManualStop(0);
          setStopMode(3);
          setStopModes(DEFAULT_STOP_MODES);
          setTrancheCount(3);
          setTrancheModes(DEFAULT_TRANCHE_MODES);
          void hydrate({ autoSelectFirst: false });
          pulse("reset");
        }}
        loadFlashing={Boolean(flashState.load)}
        resetFlashing={Boolean(flashState.reset)}
        phase={phase}
        livePrice={livePrice}
        delta={delta}
        deltaPct={deltaPct}
        account={account}
        authUser={authUser}
        onLogout={() => void logout()}
      />
      {runtimeError ? <div className="runtime-banner">{runtimeError}</div> : null}
      <div className="workspace">
        <SetupPanel
          symbol={activeSymbol || ticker}
          setup={setup}
          account={account}
          positions={positions}
          onSelectPosition={selectPosition}
          onRiskPctCommit={(value) => void commitRiskPct(value)}
        />
        <EntryPanel
          setup={setup}
          entryPrice={entryPrice || setup?.entry || 0}
          stopRef={stopRef}
          manualStop={manualStop || setup?.finalStop || 0}
          previewFlashing={Boolean(flashState.preview)}
          enterFlashing={Boolean(flashState.enter)}
          onEntryChange={setEntryPrice}
          onStopRefChange={setStopRef}
          onManualStopChange={setManualStop}
          onPreview={() => void previewTrade()}
          onEnterTrade={() => void enterTrade()}
        />
        <StopProtectionPanel
          setup={setup}
          stopMode={stopMode}
          stopModes={stopModes}
          tranches={activePosition?.tranches ?? []}
          orders={activePosition?.orders ?? []}
          executeFlashing={Boolean(flashState.stop)}
          moveToBeFlashing={Boolean(flashState.be)}
          flattenFlashing={Boolean(flashState.flatten)}
          onStopModeChange={setStopMode}
          onStopModeValueChange={(index, value) =>
            setStopModes((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)))
          }
          onExecute={() => void executeStops()}
          onMoveToBe={() => void moveToBe()}
          onFlatten={() => void flatten()}
        />
        <ProfitTakingPanel
          setup={setup}
          activePosition={activePosition}
          trancheCount={trancheCount}
          trancheModes={trancheModes}
          tranches={activePosition?.tranches ?? []}
          orders={activePosition?.orders ?? []}
          executeFlashing={Boolean(flashState.profit)}
          onTrancheCountChange={setTrancheCount}
          onTrancheModeChange={(index, value) =>
            setTrancheModes((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)))
          }
          onExecute={() => void executeProfit()}
        />
        <ActivityLog logs={logs} clearFlashing={Boolean(flashState.clear)} onClear={() => void clearLogs()} />
      </div>
    </main>
  );
}
