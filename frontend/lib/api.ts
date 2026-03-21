import type { AccountView, AuthUser, LogEntry, PositionView, SetupResponse, StopMode, TrancheMode } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    credentials: "include",
    cache: "no-store"
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || `Request failed for ${path}`);
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
  getSetup: (symbol: string) => request<SetupResponse>(`/api/setup/${symbol}`),
  getPositions: () => request<PositionView[]>("/api/positions"),
  getOrders: (symbol: string) => request(`/api/orders/${symbol}`),
  getLogs: () => request<LogEntry[]>("/api/activity-log"),
  clearLogs: () => request<{ cleared: number }>("/api/activity-log", { method: "DELETE" }),
  previewTrade: (payload: { symbol: string; entry: number; stopRef: string; stopPrice: number; riskPct: number }) =>
    request("/api/trade/preview", { method: "POST", body: JSON.stringify(payload) }),
  enterTrade: (payload: { symbol: string; entry: number; stopRef: string; stopPrice: number; trancheCount: number; trancheModes: TrancheMode[] }) =>
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
