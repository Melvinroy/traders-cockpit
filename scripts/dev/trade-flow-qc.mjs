import fs from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8010";
const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, "..", "..");
const outputDir = path.join(repoRoot, "frontend", "output", "playwright");
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

async function flattenOpenPositions() {
  const positionsResponse = await fetch(`${backendUrl}/api/positions`);
  if (!positionsResponse.ok) {
    throw new Error(`Unable to read positions from ${backendUrl}`);
  }
  const positions = await positionsResponse.json();
  for (const position of positions) {
    if (position.phase === "closed") continue;
    await fetch(`${backendUrl}/api/trade/flatten`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol: position.symbol })
    });
  }
}

async function clearActivityLog() {
  await fetch(`${backendUrl}/api/activity-log`, {
    method: "DELETE"
  });
}

async function expectStopModeRowCounts(page, expected, screenshotName) {
  const buttons = page.locator(".protect-controls .tranche-count-btn");
  const planRows = page.locator(".stop-plan-content .plan-line");
  for (const [index, key] of ["s1", "s1s2", "s1s2s3"].entries()) {
    await buttons.nth(index).click();
    let count = await planRows.count();
    const deadline = Date.now() + 3000;
    while (count !== expected[key] && Date.now() < deadline) {
      await page.waitForTimeout(100);
      count = await planRows.count();
    }
    if (count !== expected[key]) {
      throw new Error(`Stop mode ${key} expected ${expected[key]} rows but found ${count}.`);
    }
  }
  await page.screenshot({ path: path.join(outputDir, screenshotName), fullPage: true });
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });
  await flattenOpenPositions();
  await clearActivityLog();

  const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for flow QC at ${frontendUrl}.`);
  }

  await page.getByRole("button", { name: "RESET" }).click();
  await page.getByRole("textbox").fill("MSFT");
  await page.getByRole("button", { name: /LOAD SETUP/ }).click();
  await page.locator(".state-display").filter({ hasText: "SETUP LOADED" }).waitFor({ timeout: 15000 });

  await page.getByRole("button", { name: /\u2197 ENTER TRADE|ENTER TRADE/ }).click();
  await page.locator(".state-display").filter({ hasText: "TRADE ENTERED" }).waitFor({ timeout: 15000 });
  await expectStopModeRowCounts(page, { s1: 1, s1s2: 2, s1s2s3: 3 }, "baseline-stop-mode-preview.png");
  await page.screenshot({ path: path.join(outputDir, "baseline-trade-entered.png"), fullPage: true });

  const executeButtons = page.getByRole("button", { name: "EXECUTE" });
  await executeButtons.nth(0).click();
  await page.locator(".state-display").filter({ hasText: "PROTECTED" }).waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-protected.png"), fullPage: true });

  await executeButtons.nth(1).click();
  await page.locator(".state-display").filter({ hasText: /P2 DONE|RUNNER ONLY|CLOSED/ }).waitFor({ timeout: 15000 });
  await expectStopModeRowCounts(page, { s1: 1, s1s2: 2, s1s2s3: 3 }, "baseline-stop-mode-active.png");
  await page.screenshot({ path: path.join(outputDir, "baseline-profit-flow.png"), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Trade flow QC captured in ${outputDir}`);
