import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3000";
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8000";
const authUsername = process.env.QC_AUTH_USERNAME || "admin";
const authPassword = process.env.QC_AUTH_PASSWORD || "admin123!";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const outputDir = path.join(repoRoot, "frontend", "output", "playwright");
const screenshotPath = path.join(outputDir, "docker-local-paper-smoke.png");
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [repoRoot, path.join(repoRoot, "frontend")]
});
const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
const { chromium } = playwrightModule.default ?? playwrightModule;

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function loginBackend() {
  const response = await fetch(`${backendUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: authUsername, password: authPassword })
  });
  if (!response.ok) {
    throw new Error(`Unable to authenticate against ${backendUrl}`);
  }
  const cookie = response.headers.get("set-cookie");
  if (!cookie) {
    throw new Error("Missing auth cookie from backend login.");
  }
  return cookie.split(";")[0];
}

async function fetchJson(pathname, init = {}) {
  const response = await fetch(`${backendUrl}${pathname}`, init);
  const body = await response.text();
  const payload = body ? JSON.parse(body) : null;
  if (!response.ok) {
    throw new Error(typeof payload?.detail === "string" ? payload.detail : `Request failed for ${pathname}`);
  }
  return payload;
}

async function loginUiIfNeeded(page) {
  const loginTitle = page.getByText("Session Required");
  if ((await loginTitle.count()) === 0) return;
  await page.getByLabel("Username").fill(authUsername);
  await page.getByLabel("Password").fill(authPassword);
  await page.getByRole("button", { name: "SIGN IN" }).click();
  await page.getByText("Setup Parameters").waitFor({ timeout: 15000 });
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });

  const authCookie = await loginBackend();
  const account = await fetchJson("/api/account", { headers: { Cookie: authCookie } });
  if (account.effective_mode !== "alpaca_paper") {
    throw new Error(`Expected alpaca_paper mode, got ${account.effective_mode}`);
  }
  if (account.allow_live_trading !== false) {
    throw new Error("Local paper mode must keep live trading disabled.");
  }

  const setup = await fetchJson("/api/setup/MSFT", { headers: { Cookie: authCookie } });
  if (setup.quoteProvider !== "alpaca" || setup.quoteIsReal !== true) {
    throw new Error(`Expected a real Alpaca quote, got ${JSON.stringify({
      quoteProvider: setup.quoteProvider,
      quoteIsReal: setup.quoteIsReal,
      fallbackReason: setup.fallbackReason
    })}`);
  }
  if (setup.executionProvider !== "alpaca_paper") {
    throw new Error(`Expected alpaca_paper execution, got ${setup.executionProvider}`);
  }
  if (!setup.sessionState || !setup.quoteState) {
    throw new Error("Setup response is missing sessionState/quoteState metadata.");
  }
  if (typeof setup.lod !== "number" || typeof setup.atr14 !== "number" || setup.atr14 <= 0) {
    throw new Error("Setup response is missing real LoD/ATR values.");
  }
  if (!["lod", "manual"].includes(setup.stopReferenceDefault)) {
    throw new Error(`Unexpected default stop reference ${setup.stopReferenceDefault}`);
  }
  if (typeof setup.accountEquity !== "number" || setup.accountEquity <= 0 || setup.equitySource !== "alpaca_account") {
    throw new Error("Setup sizing is not using broker-backed equity.");
  }

  const enter = await fetchJson("/api/trade/enter", {
    method: "POST",
    headers: { "Content-Type": "application/json", Cookie: authCookie },
    body: JSON.stringify({
      symbol: "MSFT",
      entry: setup.entry,
      stopRef: "lod",
      stopPrice: setup.finalStop,
      trancheCount: 3,
      offHoursMode: setup.sessionState === "regular_open" ? null : "queue_for_open",
      trancheModes: [
        { mode: "limit", trail: 2, trailUnit: "$", target: "1R", manualPrice: null },
        { mode: "limit", trail: 2, trailUnit: "$", target: "2R", manualPrice: null },
        { mode: "runner", trail: 2, trailUnit: "$", target: "3R", manualPrice: null }
      ]
    })
  });
  if (!enter.orders?.[0]?.brokerOrderId) {
    throw new Error("Entry order did not return a real brokerOrderId.");
  }
  if (enter.phase === "entry_pending") {
    const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
    if (!response || response.status() >= 400) {
      throw new Error(`Frontend root failed to load at ${frontendUrl}.`);
    }
    await loginUiIfNeeded(page);
    await page.getByText("Setup Parameters").waitFor({ timeout: 15000 });
    await page.screenshot({ path: screenshotPath, fullPage: true });
  } else {
    const protectedView = await fetchJson("/api/trade/stops", {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: authCookie },
      body: JSON.stringify({
        symbol: "MSFT",
        stopMode: 3,
        stopModes: [
          { mode: "stop", pct: null },
          { mode: "stop", pct: null },
          { mode: "stop", pct: null }
        ]
      })
    });
    const stopOrders = protectedView.orders.filter((order) => order.type === "STOP");
    if (stopOrders.length !== 3 || stopOrders.some((order) => !order.brokerOrderId)) {
      throw new Error("Stop execution did not create three real broker-backed stop orders.");
    }

    const profitView = await fetchJson("/api/trade/profit", {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: authCookie },
      body: JSON.stringify({
        symbol: "MSFT",
        trancheModes: [
          { mode: "limit", trail: 2, trailUnit: "$", target: "1R", manualPrice: null },
          { mode: "limit", trail: 2, trailUnit: "$", target: "2R", manualPrice: null },
          { mode: "runner", trail: 2, trailUnit: "$", target: "3R", manualPrice: null }
        ]
      })
    });
    const profitOrders = profitView.orders.filter((order) => order.type === "LMT" || order.type === "TRAIL");
    if (profitOrders.length < 3 || profitOrders.some((order) => !order.brokerOrderId)) {
      throw new Error("Profit execution did not create real broker-backed limit/trailing orders.");
    }

    const flattened = await fetchJson("/api/trade/flatten", {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: authCookie },
      body: JSON.stringify({ symbol: "MSFT" })
    });
    const flattenOrders = flattened.orders.filter((order) => order.type === "MKT" && order.tranche.startsWith("T"));
    if (flattenOrders.length === 0) {
      throw new Error("Flatten did not create local flatten market orders.");
    }

    const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
    if (!response || response.status() >= 400) {
      throw new Error(`Frontend root failed to load at ${frontendUrl}.`);
    }
    await loginUiIfNeeded(page);
    await page.getByText("Setup Parameters").waitFor({ timeout: 15000 });
    await page.screenshot({ path: screenshotPath, fullPage: true });
  }
} finally {
  await browser.close();
}

console.log(`Docker local paper smoke passed: ${screenshotPath}`);
