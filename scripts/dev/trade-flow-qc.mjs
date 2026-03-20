import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const backendUrl = process.env.BACKEND_URL || "http://127.0.0.1:8010";
const outputDir = path.resolve(process.cwd(), "output", "playwright");
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [process.cwd(), path.resolve(process.cwd(), "frontend")]
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

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });
  await flattenOpenPositions();

  const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for flow QC at ${frontendUrl}.`);
  }

  await page.getByRole("button", { name: "RESET" }).click();
  await page.getByRole("textbox").fill("MSFT");
  await page.getByRole("button", { name: /LOAD SETUP/ }).click();
  await page.getByText("SETUP LOADED").waitFor({ timeout: 15000 });

  await page.getByRole("button", { name: /\u2197 ENTER TRADE|ENTER TRADE/ }).click();
  await page.getByText("TRADE ENTERED").waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-trade-entered.png"), fullPage: true });

  const executeButtons = page.getByRole("button", { name: "EXECUTE" });
  await executeButtons.nth(0).click();
  await page.getByText("PROTECTED").waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-protected.png"), fullPage: true });

  await executeButtons.nth(1).click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(outputDir, "baseline-profit-flow.png"), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Trade flow QC captured in ${outputDir}`);
