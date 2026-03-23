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
}

async function flattenOpenPositions() {
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
}

async function clearActivityLog() {
  const authCookie = await loginBackend();
  await fetch(`${backendUrl}/api/activity-log`, {
    method: "DELETE",
    headers: { Cookie: authCookie },
  });
}

function normalizeStopLabel(value) {
  return (value ?? "").replaceAll("Â·", "·").trim();
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
    { timeout: 5000 }
  );
  await symbolInput.press("Enter");
}

async function expectStopModeRowCounts(page, expected, screenshotName) {
  const rows = page.locator(".stop-plan-content .plan-line:not(.stop-action-line)");
  const activeButton = page.locator(".protect-controls .tranche-count-btn.active");
  const labels = ["S1", `S1\u00B7S2`, `S1\u00B7S2\u00B7S3`];
  for (const [index, key] of ["s1", "s1s2", "s1s2s3"].entries()) {
    let activeText = await activeButton.allTextContents();
    if (normalizeStopLabel(activeText[0]) !== labels[index]) {
      await page.locator(".protect-controls .tranche-count-btn").nth(index).click({ force: true });
    }
    await page.waitForTimeout(500);
    activeText = await activeButton.allTextContents();
    const count = await rows.count();
    if (normalizeStopLabel(activeText[0]) !== labels[index] || count !== expected[key]) {
      throw new Error(
        `Stop mode preview mismatch for ${key}: expected label ${labels[index]} and ${expected[key]} rows, got label ${activeText[0] ?? "<none>"} and ${count} rows.`,
      );
    }
  }
  await page.screenshot({ path: path.join(outputDir, screenshotName), fullPage: true });
}

async function expectCoverage(page, expected) {
  const rows = page.locator(".stop-plan-content .plan-line:not(.stop-action-line)");
  for (let index = 0; index < expected.length; index += 1) {
    let rowText = (await rows.nth(index).textContent()) ?? "";
    const deadline = Date.now() + 3000;
    while (expected[index].some((value) => !rowText.includes(value)) && Date.now() < deadline) {
      await page.waitForTimeout(100);
      rowText = (await rows.nth(index).textContent()) ?? "";
    }
    if (expected[index].some((value) => !rowText.includes(value))) {
      throw new Error(`Coverage mismatch at row ${index + 1}: expected ${JSON.stringify(expected[index])}, got ${JSON.stringify(rowText)}`);
    }
  }
}

async function expectStatuses(page, expected) {
  const selector = ".stop-plan-content .plan-line:not(.stop-action-line) .plan-status";
  let statuses = await page.locator(selector).evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ""));
  const deadline = Date.now() + 3000;
  while (JSON.stringify(statuses) !== JSON.stringify(expected) && Date.now() < deadline) {
    await page.waitForTimeout(100);
    statuses = await page.locator(selector).evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ""));
  }
  if (JSON.stringify(statuses) !== JSON.stringify(expected)) {
    throw new Error(`Status mismatch: expected ${JSON.stringify(expected)}, got ${JSON.stringify(statuses)}`);
  }
}

async function readStatuses(page) {
  const selector = ".stop-plan-content .plan-line:not(.stop-action-line) .plan-status";
  return page.locator(selector).evaluateAll((nodes) => nodes.map((node) => node.textContent?.trim() ?? ""));
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });
  await flattenOpenPositions();
  await clearActivityLog();
  await seedAuthSession(page);

  const response = await page.goto(frontendUrl, { waitUntil: "load" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for flow QC at ${frontendUrl}.`);
  }

  await page.getByText("Setup Parameters").waitFor({ timeout: 30000 });
  await loadSetup(page, "MSFT");
  await page.locator(".state-display").filter({ hasText: "SETUP LOADED" }).waitFor({ timeout: 15000 });

  await page.getByRole("button", { name: /\u2197 ENTER TRADE|ENTER TRADE/ }).click();
  await page.locator(".state-display").filter({ hasText: "TRADE ENTERED" }).waitFor({ timeout: 15000 });
  await expectStopModeRowCounts(page, { s1: 1, s1s2: 2, s1s2s3: 3 }, "baseline-stop-mode-preview.png");
  await expectCoverage(page, [["T1"], ["T2"], ["T3"]]);
  await expectStatuses(page, ["PREVIEW", "PREVIEW", "PREVIEW"]);
  await page.screenshot({ path: path.join(outputDir, "baseline-trade-entered.png"), fullPage: true });

  const stopExecuteButton = page.locator(".protect-header .stop-ok-btn");
  const profitExecuteButton = page.locator(".profit-header .stop-ok-btn");
  await stopExecuteButton.waitFor({ state: "visible", timeout: 15000 });
  await stopExecuteButton.click({ force: true });
  await page.locator(".state-display").filter({ hasText: "PROTECTED" }).waitFor({ timeout: 15000 });
  await expectStatuses(page, ["ACTIVE", "ACTIVE", "ACTIVE"]);
  await page.screenshot({ path: path.join(outputDir, "baseline-protected.png"), fullPage: true });

  await profitExecuteButton.waitFor({ state: "visible", timeout: 15000 });
  await profitExecuteButton.click({ force: true });
  await page.locator(".state-display").filter({ hasText: /P2 DONE|RUNNER ONLY|CLOSED/ }).waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-stop-mode-active.png"), fullPage: true });
  const finalStatuses = await readStatuses(page);
  const acceptableFinalStates = [
    JSON.stringify(["CANCELED", "CANCELED", "ACTIVE"]),
    JSON.stringify(["CANCELED", "CANCELED", "CANCELED"]),
  ];
  if (!acceptableFinalStates.includes(JSON.stringify(finalStatuses))) {
    throw new Error(`Unexpected final stop statuses: ${JSON.stringify(finalStatuses)}`);
  }
  await page.screenshot({ path: path.join(outputDir, "baseline-profit-flow.png"), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Trade flow QC captured in ${outputDir}`);
