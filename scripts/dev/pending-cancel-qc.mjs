import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8010";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const outputDir = path.join(repoRoot, "frontend", "output", "playwright");
const authUsername = process.env.QC_AUTH_USERNAME || "admin";
const authPassword = process.env.QC_AUTH_PASSWORD || "change-me-admin";
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [repoRoot, path.join(repoRoot, "frontend")],
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
    body: JSON.stringify({ username: authUsername, password: authPassword }),
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

async function seedAuthSession(page) {
  const cookiePair = await loginBackend();
  const separator = cookiePair.indexOf("=");
  const cookieName = cookiePair.slice(0, separator);
  const cookieValue = cookiePair.slice(separator + 1);
  const frontend = new URL(frontendUrl);
  await page.context().addCookies([
    {
      name: cookieName,
      value: cookieValue,
      domain: frontend.hostname,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
  return cookiePair;
}

async function clearActiveState() {
  const authCookie = await loginBackend();
  const positionsResponse = await fetch(`${backendUrl}/api/positions`, {
    headers: { Cookie: authCookie },
  });
  if (!positionsResponse.ok) {
    throw new Error(`Unable to read positions from ${backendUrl}`);
  }
  const positions = await positionsResponse.json();
  for (const position of positions) {
    if (position.phase === "closed") continue;
    await fetch(`${backendUrl}/api/trade/flatten`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Cookie: authCookie },
      body: JSON.stringify({ symbol: position.symbol }),
    });
  }

  const ordersResponse = await fetch(`${backendUrl}/api/orders`, {
    headers: { Cookie: authCookie },
  });
  if (!ordersResponse.ok) {
    throw new Error(`Unable to read recent orders from ${backendUrl}`);
  }
  const recentOrders = await ordersResponse.json();
  for (const order of recentOrders) {
    if (!order.cancelable || !order.brokerOrderId) continue;
    await fetch(`${backendUrl}/api/orders/${order.brokerOrderId}`, {
      method: "DELETE",
      headers: { Cookie: authCookie },
    });
  }

  await fetch(`${backendUrl}/api/activity-log`, {
    method: "DELETE",
    headers: { Cookie: authCookie },
  });
}

async function loadSetup(page, symbol = "MSFT") {
  const symbolInput = page.locator("#tickerInput");
  await symbolInput.waitFor({ state: "visible", timeout: 15000 });
  await symbolInput.fill(symbol);
  await page.waitForFunction(
    (value) => {
      const input = document.querySelector("#tickerInput");
      return input instanceof HTMLInputElement && input.value === value;
    },
    symbol,
    { timeout: 5000 },
  );
  await symbolInput.press("Enter");
}

function pendingLimitFrom(entryText, stopText) {
  const entry = Number(entryText);
  const stop = Number(stopText);
  if (!Number.isFinite(entry) || entry <= 0 || !Number.isFinite(stop) || stop <= 0) {
    throw new Error(`Unable to derive pending limit from entry=${entryText} stop=${stopText}`);
  }
  const midpoint = Number((((entry + stop) / 2)).toFixed(2));
  if (midpoint <= stop) {
    return Number((stop + 0.1).toFixed(2));
  }
  return midpoint;
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });
  await clearActiveState();
  await seedAuthSession(page);

  const response = await page.goto(frontendUrl, { waitUntil: "load" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for pending cancel QC at ${frontendUrl}.`);
  }

  await page.getByText("Setup Parameters").waitFor({ timeout: 30000 });
  await loadSetup(page, "MSFT");
  await page.locator(".state-display").filter({ hasText: "SETUP LOADED" }).waitFor({ timeout: 15000 });

  await page.locator("#entryOrderType").selectOption("limit");
  await page.locator("#entryTimeInForce").selectOption("day");
  await page.locator("#entryOrderClass").selectOption("simple");

  const entryValue = await page.locator("#heroEntry").inputValue();
  const stopValue = await page.locator(".hero-stop-price").textContent();
  const pendingLimit = pendingLimitFrom(entryValue, stopValue ?? "");
  await page.locator("#entryLimitPrice").fill(String(pendingLimit));

  await page.getByRole("button", { name: /\u2197 ENTER TRADE|ENTER TRADE/ }).click();
  await page.locator(".state-display").filter({ hasText: "ENTRY SUBMITTED" }).waitFor({ timeout: 15000 });

  await page.getByRole("button", { name: "Open / Working", exact: true }).click();
  const cancelButton = page.locator(".orders-cancel-btn").first();
  await cancelButton.waitFor({ state: "visible", timeout: 15000 });
  const pendingRow = cancelButton.locator("xpath=ancestor::tr[1]");
  const brokerOrderId = await pendingRow.getAttribute("title");
  if (!brokerOrderId) {
    throw new Error("Pending order row is missing broker order id.");
  }

  await cancelButton.click();
  await page.waitForTimeout(500);

  await page.getByRole("button", { name: "All", exact: true }).click();
  const canceledRow = page.locator(`tr[title="${brokerOrderId}"]`).first();
  await canceledRow.waitFor({ state: "visible", timeout: 15000 });
  await page.waitForFunction(
    (orderId) => {
      const row = document.querySelector(`tr[title="${orderId}"]`);
      return row?.textContent?.includes("CANCELED") ?? false;
    },
    brokerOrderId,
    { timeout: 15000 },
  );

  await page.screenshot({ path: path.join(outputDir, "pending-cancel-flow.png"), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Pending cancel QC captured in ${outputDir}`);
