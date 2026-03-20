"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ActivityLog } from "@/components/ActivityLog";
import { CockpitHeader } from "@/components/CockpitHeader";
import { EntryPanel } from "@/components/EntryPanel";
import { ProfitTakingPanel } from "@/components/ProfitTakingPanel";
import { SetupPanel } from "@/components/SetupPanel";
import { StopProtectionPanel } from "@/components/StopProtectionPanel";
import { api } from "@/lib/api";
import type { AccountView, LogEntry, PositionView, SetupResponse, StopMode, TrancheMode } from "@/lib/types";

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

  const subscribePrice = useCallback((symbol: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "subscribe_price", symbol }));
    }
  }, []);

  const applyPositionState = useCallback((position: PositionView) => {
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
  }, [subscribePrice]);

  const hydrate = useCallback(async (options?: { autoSelectFirst?: boolean }) => {
    const autoSelectFirst = options?.autoSelectFirst ?? false;
    const [accountView, positionRows, logRows] = await Promise.all([
      api.getAccount(),
      api.getPositions(),
      api.getLogs()
    ]);
    setAccount(accountView);
    setPositions(positionRows);
    setLogs(logRows);

    if (activeSymbolRef.current) {
      const active = positionRows.find((position) => position.symbol === activeSymbolRef.current);
      if (active) {
        applyPositionState(active);
        return;
      }
    }

    if (autoSelectFirst && !activeSymbolRef.current && !setupLoadedRef.current && positionRows[0]) {
      applyPositionState(positionRows[0]);
    }
  }, [applyPositionState]);

  const selectPosition = useCallback((symbol: string, source: PositionView[] = positions) => {
    const position = source.find((item) => item.symbol === symbol);
    if (!position) return;
    applyPositionState(position);
  }, [applyPositionState, positions]);

  useEffect(() => {
    void hydrate({ autoSelectFirst: true });
  }, [hydrate]);

  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL ?? "ws://127.0.0.1:8010/ws/cockpit";
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onopen = () => {
      if (activeSymbolRef.current) {
        ws.send(JSON.stringify({ action: "subscribe_price", symbol: activeSymbolRef.current }));
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
      if (payload.type === "position_update" || payload.type === "order_update" || payload.type === "log_update") {
        void hydrate({ autoSelectFirst: Boolean(activeSymbolRef.current) });
      }
    };
    return () => ws.close();
  }, [hydrate]);

  const loadSetup = useCallback(async () => {
    const nextSetup = await api.getSetup(ticker);
    activeSymbolRef.current = "";
    setupLoadedRef.current = true;
    setSetup(nextSetup);
    setEntryPrice(nextSetup.entry);
    setManualStop(nextSetup.finalStop);
    setActiveSymbol("");
    setStopMode(0);
    setStopModes(DEFAULT_STOP_MODES);
    subscribePrice(ticker);
    await hydrate({ autoSelectFirst: false });
    pulse("load");
  }, [hydrate, pulse, subscribePrice, ticker]);

  useEffect(() => {
    if (initialAutoloadRef.current) return;
    if (!account) return;
    if (setup || positions.length > 0 || activeSymbolRef.current) {
      initialAutoloadRef.current = true;
      return;
    }
    initialAutoloadRef.current = true;
    void loadSetup();
  }, [account, loadSetup, positions.length, setup]);

  async function commitRiskPct(nextRiskPct: number) {
    if (!account) return;
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
  }

  async function previewTrade() {
    if (!setup) return;
    await api.previewTrade({
      symbol: ticker,
      entry: entryPrice,
      stopRef,
      stopPrice: stopRef === "manual" ? manualStop : setup.finalStop,
      riskPct: account?.risk_pct ?? setup.riskPct
    });
    await hydrate({ autoSelectFirst: false });
    pulse("preview");
  }

  async function enterTrade() {
    if (!setup) return;
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
  }

  async function executeStops() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    const position = await api.applyStops({ symbol, stopMode, stopModes });
    await hydrate({ autoSelectFirst: false });
    selectPosition(position.symbol);
    pulse("stop");
  }

  async function executeProfit() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    const position = await api.executeProfit({ symbol, trancheModes });
    await hydrate({ autoSelectFirst: false });
    selectPosition(position.symbol);
    pulse("profit");
  }

  async function moveToBe() {
    if (!activeSymbol) return;
    const position = await api.moveToBe(activeSymbol);
    await hydrate({ autoSelectFirst: false });
    selectPosition(position.symbol);
    pulse("be");
  }

  async function flatten() {
    if (!activeSymbol) return;
    const position = await api.flatten(activeSymbol);
    await hydrate({ autoSelectFirst: false });
    if (position.phase === "closed") {
      activeSymbolRef.current = "";
      setActiveSymbol("");
    }
    pulse("flatten");
  }

  async function clearLogs() {
    await api.clearLogs();
    await hydrate({ autoSelectFirst: false });
    pulse("clear");
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
          setTicker("AAPL");
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
      />
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
