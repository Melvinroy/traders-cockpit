export type StopMode = { mode: "stop" | "be"; pct: number | null };

export type TrancheMode = {
  mode: "limit" | "runner";
  trail: number;
  trailUnit: "$" | "%";
  target: "1R" | "2R" | "3R" | "Manual";
  manualPrice: number | null;
};

export type Tranche = {
  id: string;
  qty: number;
  stop: number;
  target?: number | null;
  status: "active" | "sold" | "canceled";
  mode: "limit" | "runner";
  trail: number;
  trailUnit: "$" | "%";
  label: string;
  runnerStop?: number | null;
};

export type OrderView = {
  id: string;
  type: string;
  qty: number;
  origQty: number;
  price: number;
  status: string;
  tranche: string;
  coveredTranches: string[];
  parentId?: string | null;
  brokerOrderId?: string | null;
  createdAt?: string | null;
  filledAt?: string | null;
  fillPrice?: number | null;
};

export type SetupResponse = {
  symbol: string;
  provider: string;
  providerState: string;
  quoteProvider: string;
  technicalsProvider: string;
  executionProvider: string;
  quoteIsReal: boolean;
  technicalsAreFallback: boolean;
  fallbackReason?: string | null;
  quoteTimestamp?: string | null;
  entryBasis: string;
  stopReferenceDefault: string;
  bid: number;
  ask: number;
  last: number;
  lod: number;
  hod: number;
  prev_close: number;
  atr14: number;
  sma10: number;
  sma50: number;
  sma200: number;
  sma200_prev: number;
  rvol: number;
  days_to_cover: number;
  entry: number;
  finalStop: number;
  r1: number;
  r2: number;
  r3: number;
  shares: number;
  dollarRisk: number;
  perShareRisk: number;
  riskPct: number;
  accountEquity: number;
  atrExtension: number;
  extFrom10Ma: number;
};

export type PositionView = {
  symbol: string;
  phase: string;
  livePrice: number;
  setup: SetupResponse;
  tranches: Tranche[];
  orders: OrderView[];
  trancheModes: TrancheMode[];
  stopModes: StopMode[];
  rootOrderId?: string | null;
  stopMode: number;
  trancheCount: number;
};

export type AccountView = {
  equity: number;
  buying_power: number;
  risk_pct: number;
  mode: string;
  effective_mode: string;
  daily_realized_pnl: number;
  allow_live_trading: boolean;
  max_position_notional_pct: number;
  daily_loss_limit_pct: number;
  max_open_positions: number;
  live_disabled_reason?: string | null;
};

export type LogEntry = {
  id: number;
  symbol?: string | null;
  tag: string;
  message: string;
  created_at: string;
};

export type AuthUser = {
  username: string;
  role: string;
  expires_at?: string | null;
};
