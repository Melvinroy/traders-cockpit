import type {
  AccountView,
  AuthUser,
  EntryOrderDraft,
  LogEntry,
  OffHoursMode,
  OrderView,
  PositionView,
  SetupResponse,
  StopMode,
  TradePreviewResponse,
  TrancheMode,
} from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function formatValidationDetail(detail: unknown): string | null {
  if (!Array.isArray(detail) || detail.length === 0) return null;
  const parts = detail
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const message = typeof item.msg === "string" ? item.msg : null;
      const location = Array.isArray(item.loc)
        ? item.loc.filter((value: unknown) => typeof value === "string" || typeof value === "number").join(".")
        : null;
      if (!message) return null;
      return location ? `${location}: ${message}` : message;
    })
    .filter((item): item is string => Boolean(item));
  return parts.length ? parts.join("; ") : null;
}

async function readErrorMessage(path: string, response: Response): Promise<string> {
  const raw = (await response.text()).trim();
  if (!raw) {
    return `Request failed for ${path}`;
  }

  try {
    const parsed = JSON.parse(raw) as { detail?: unknown; message?: unknown };
    if (typeof parsed.detail === "string") {
      return parsed.detail === "Not Found" ? "Requested resource was not found." : parsed.detail;
    }
    const validationMessage = formatValidationDetail(parsed.detail);
    if (validationMessage) {
      return validationMessage;
    }
    if (typeof parsed.message === "string") {
      return parsed.message;
    }
  } catch {
    if (raw === "Not Found") {
      return "Requested resource was not found.";
    }
  }

  return raw;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      },
      credentials: "include",
      cache: "no-store"
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError(0, "Backend is unavailable.");
    }
    throw error;
  }
  if (!response.ok) {
    const detail = await readErrorMessage(path, response);
    throw new ApiError(response.status, detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  me: () => request<AuthUser>("/api/auth/me"),
  login: (payload: { username: string; password: string }) =>
    request<AuthUser>("/api/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  getAccount: () => request<AccountView>("/api/account"),
  updateAccount: (payload: { equity: number; risk_pct: number; mode: string }) =>
    request<AccountView>("/api/account/settings", { method: "PUT", body: JSON.stringify(payload) }),
  getSetup: (symbol: string, signal?: AbortSignal) => request<SetupResponse>(`/api/setup/${symbol}`, { signal }),
  getPositions: () => request<PositionView[]>("/api/positions"),
  getOrders: (symbol: string) => request<OrderView[]>(`/api/orders/${symbol}`),
  getRecentOrders: () => request<OrderView[]>("/api/orders"),
  cancelOrder: (brokerOrderId: string) => request<OrderView>(`/api/orders/${brokerOrderId}`, { method: "DELETE" }),
  getLogs: () => request<LogEntry[]>("/api/activity-log"),
  clearLogs: () => request<{ cleared: number }>("/api/activity-log", { method: "DELETE" }),
  previewTrade: (payload: { symbol: string; entry: number; stopRef: string; stopPrice: number; riskPct: number; order: EntryOrderDraft }) =>
    request<TradePreviewResponse>("/api/trade/preview", { method: "POST", body: JSON.stringify(payload) }),
  enterTrade: (payload: { symbol: string; entry: number; stopRef: string; stopPrice: number; trancheCount: number; trancheModes: TrancheMode[]; offHoursMode?: OffHoursMode | null; order: EntryOrderDraft }) =>
    request<PositionView>("/api/trade/enter", { method: "POST", body: JSON.stringify(payload) }),
  applyStops: (payload: { symbol: string; stopMode: number; stopModes: StopMode[] }) =>
    request<PositionView>("/api/trade/stops", { method: "POST", body: JSON.stringify(payload) }),
  executeProfit: (payload: { symbol: string; trancheModes: TrancheMode[] }) =>
    request<PositionView>("/api/trade/profit", { method: "POST", body: JSON.stringify(payload) }),
  moveToBe: (symbol: string) =>
    request<PositionView>("/api/trade/move_to_be", { method: "POST", body: JSON.stringify({ symbol }) }),
  flatten: (symbol: string) =>
    request<PositionView>("/api/trade/flatten", { method: "POST", body: JSON.stringify({ symbol }) })
};
