export type StopMode = { mode: "stop" | "be"; pct: number | null };

export type EntrySide = "buy" | "sell";
export type EntryOrderType = "market" | "limit" | "stop" | "stop_limit";
export type TimeInForce = "day" | "gtc" | "ioc" | "fok" | "opg" | "cls";
export type OrderClass = "simple" | "bracket" | "oco" | "oto";
export type OtoExitSide = "stop_loss" | "take_profit";

export type TakeProfitDraft = {
  limitPrice: number | null;
};

export type StopLossDraft = {
  stopPrice: number | null;
  limitPrice: number | null;
};

export type EntryOrderDraft = {
  side: EntrySide;
  orderType: EntryOrderType;
  timeInForce: TimeInForce;
  orderClass: OrderClass;
  extendedHours: boolean;
  limitPrice: number | null;
  stopPrice: number | null;
  otoExitSide: OtoExitSide;
  takeProfit: TakeProfitDraft | null;
  stopLoss: StopLossDraft | null;
};

export type TrancheMode = {
  mode: "limit" | "runner";
  allocationPct?: number | null;
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
  exitPrice?: number | null;
  exitFilledAt?: string | null;
  exitOrderType?: string | null;
  mode: "limit" | "runner";
  trail: number;
  trailUnit: "$" | "%";
  label: string;
  runnerStop?: number | null;
};

export type OrderView = {
  id: string;
  symbol: string;
  side?: string | null;
  type: string;
  qty: number;
  origQty: number;
  filledQty: number;
  remainingQty: number;
  price: number;
  status: string;
  tranche: string;
  coveredTranches: string[];
  parentId?: string | null;
  brokerOrderId?: string | null;
  cancelable: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
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
  sessionState: "regular_open" | "overnight" | "pre_market" | "after_hours" | "closed";
  quoteState: "live_quote" | "cached_quote" | "quote_unavailable";
  entryBasis: string;
  stopReferenceDefault: "lod" | "atr" | "manual";
  lodIsValid: boolean;
  atrIsValid: boolean;
  lodStop: number;
  atrStop: number;
  manualStopWarning?: string | null;
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
  accountBuyingPower: number;
  accountCash?: number | null;
  equitySource: string;
  sizingWarning?: string | null;
  buyingPowerNote?: string | null;
  atrExtension: number;
  extFrom10Ma: number;
  entryOrder?: EntryOrderDraft;
};

export type TradePreviewResponse = {
  symbol: string;
  entry: number;
  finalStop: number;
  perShareRisk: number;
  shares: number;
  dollarRisk: number;
  sizingWarning?: string | null;
  orderType?: EntryOrderType;
  timeInForce?: TimeInForce;
  orderClass?: OrderClass;
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

export type OffHoursMode = "queue_for_open" | "extended_hours_limit";

export type AccountView = {
  equity: number;
  buying_power: number;
  cash?: number | null;
  risk_pct: number;
  mode: string;
  effective_mode: string;
  equity_source: string;
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
