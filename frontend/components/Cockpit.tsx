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
  { mode: "stop", pct: 33 },
  { mode: "stop", pct: 66 },
  { mode: "stop", pct: 100 }
];

const DEFAULT_TRANCHE_MODES: TrancheMode[] = [
  { mode: "limit", trail: 2, trailUnit: "$", target: "1R", manualPrice: null },
  { mode: "limit", trail: 2, trailUnit: "$", target: "2R", manualPrice: null },
  { mode: "runner", trail: 2, trailUnit: "$", target: "3R", manualPrice: null }
];

export function Cockpit() {
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

  const hydrate = useCallback(async () => {
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
        setSetup(active.setup as SetupResponse);
        setEntryPrice(active.setup.entry);
        setManualStop(active.setup.finalStop);
        setStopMode(active.stopMode || 3);
        setStopModes(active.stopModes.length ? active.stopModes : DEFAULT_STOP_MODES);
        setTrancheCount(active.trancheCount || 3);
        setTrancheModes(active.trancheModes.length ? active.trancheModes : DEFAULT_TRANCHE_MODES);
        return;
      }
    }

    if (!activeSymbolRef.current && positionRows[0]) {
      const first = positionRows[0];
      setActiveSymbol(first.symbol);
      setTicker(first.symbol);
      setSetup(first.setup as SetupResponse);
      setEntryPrice(first.setup.entry);
      setManualStop(first.setup.finalStop);
      setStopMode(first.stopMode || 3);
      setStopModes(first.stopModes.length ? first.stopModes : DEFAULT_STOP_MODES);
      setTrancheCount(first.trancheCount || 3);
      setTrancheModes(first.trancheModes.length ? first.trancheModes : DEFAULT_TRANCHE_MODES);
    }
  }, []);

  const subscribePrice = useCallback((symbol: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "subscribe_price", symbol }));
    }
  }, []);

  const selectPosition = useCallback((symbol: string, source: PositionView[] = positions) => {
    const position = source.find((item) => item.symbol === symbol);
    if (!position) return;
    setActiveSymbol(symbol);
    setTicker(symbol);
    setSetup(position.setup as SetupResponse);
    setEntryPrice(position.setup.entry);
    setManualStop(position.setup.finalStop);
    setStopMode(position.stopMode || 3);
    setStopModes(position.stopModes.length ? position.stopModes : DEFAULT_STOP_MODES);
    setTrancheCount(position.trancheCount || 3);
    setTrancheModes(position.trancheModes.length ? position.trancheModes : DEFAULT_TRANCHE_MODES);
    subscribePrice(symbol);
  }, [positions, subscribePrice]);

  useEffect(() => {
    void hydrate();
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
      if (payload.type === "price" && typeof payload.symbol === "string") {
        setPositions((current) =>
          current.map((position) =>
            position.symbol === payload.symbol
              ? { ...position, livePrice: Number(payload.last ?? position.livePrice) }
              : position
          )
        );
      }
      if (payload.type === "position_update") {
        void hydrate();
      }
    };
    return () => ws.close();
  }, [hydrate]);

  async function loadSetup() {
    const nextSetup = await api.getSetup(ticker);
    setSetup(nextSetup);
    setEntryPrice(nextSetup.entry);
    setManualStop(nextSetup.finalStop);
    setActiveSymbol("");
    subscribePrice(ticker);
    await hydrate();
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
    await hydrate();
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
    await hydrate();
    selectPosition(position.symbol, [position, ...positions]);
  }

  async function executeStops() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    const position = await api.applyStops({ symbol, stopMode, stopModes });
    await hydrate();
    selectPosition(position.symbol);
  }

  async function executeProfit() {
    const symbol = activeSymbol || ticker;
    if (!symbol) return;
    const position = await api.executeProfit({ symbol, trancheModes });
    await hydrate();
    selectPosition(position.symbol);
  }

  async function moveToBe() {
    if (!activeSymbol) return;
    const position = await api.moveToBe(activeSymbol);
    await hydrate();
    selectPosition(position.symbol);
  }

  async function flatten() {
    if (!activeSymbol) return;
    const position = await api.flatten(activeSymbol);
    await hydrate();
    if (position.phase === "closed") {
      setActiveSymbol("");
    }
  }

  async function clearLogs() {
    await api.clearLogs();
    await hydrate();
  }

  return (
    <main>
      <CockpitHeader
        ticker={ticker}
        onTickerChange={setTicker}
        onLoad={() => void loadSetup()}
        onReset={() => {
          setSetup(null);
          setActiveSymbol("");
          setTicker("AAPL");
          setEntryPrice(0);
          setManualStop(0);
          setStopMode(3);
          setStopModes(DEFAULT_STOP_MODES);
          setTrancheCount(3);
          setTrancheModes(DEFAULT_TRANCHE_MODES);
          void hydrate();
        }}
        phase={phase}
        livePrice={livePrice}
        delta={delta}
        deltaPct={deltaPct}
        account={account}
      />
      <div className="workspace">
        <SetupPanel symbol={activeSymbol || ticker} setup={setup} positions={positions} onSelectPosition={selectPosition} />
        <EntryPanel
          setup={setup}
          entryPrice={entryPrice || setup?.entry || 0}
          stopRef={stopRef}
          manualStop={manualStop || setup?.finalStop || 0}
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
          onTrancheCountChange={setTrancheCount}
          onTrancheModeChange={(index, value) =>
            setTrancheModes((current) => current.map((item, itemIndex) => (itemIndex === index ? value : item)))
          }
          onExecute={() => void executeProfit()}
        />
        <ActivityLog logs={logs} onClear={() => void clearLogs()} />
      </div>
    </main>
  );
}
