import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const outputDir = path.resolve(process.cwd(), "output", "playwright");
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [process.cwd(), path.resolve(process.cwd(), "frontend")]
});
const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
const { chromium } = playwrightModule.default ?? playwrightModule;

function safeName(value) {
  return value.toLowerCase().replace(/[^a-z0-9-_]+/g, "-");
}

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

try {
  await fs.mkdir(outputDir, { recursive: true });

  const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for baseline capture at ${frontendUrl}.`);
  }

  await page.getByRole("button", { name: "RESET" }).click();
  await page.getByText("IDLE").waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-idle.png"), fullPage: true });

  await page.getByRole("button", { name: /LOAD SETUP/ }).click();
  await page.getByText("SETUP LOADED").waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-setup-loaded.png"), fullPage: true });

  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const phaseText = (await page.locator(".state-display").textContent())?.trim() || "unknown";
  await page.screenshot({ path: path.join(outputDir, `baseline-${safeName(phaseText)}.png`), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Fidelity baselines captured in ${outputDir}`);
