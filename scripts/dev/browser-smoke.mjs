import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const outputDir = path.resolve(process.cwd(), "output", "playwright");
const screenshotPath = path.join(outputDir, "browser-smoke.png");
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [process.cwd(), path.resolve(process.cwd(), "frontend")],
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

const browser = await launchBrowser();
const page = await browser.newPage();

try {
  await fs.mkdir(outputDir, { recursive: true });
  await page.goto(frontendUrl, { waitUntil: "networkidle" });

  if (!(await page.title()).includes("Trader's Cockpit")) {
    throw new Error("Unexpected page title during browser smoke test.");
  }

  await page.getByRole("button", { name: "LOAD SETUP" }).click();
  await page.getByText("SETUP LOADED").waitFor({ timeout: 15000 });
  await page.getByText("Suggested Entry").waitFor({ timeout: 15000 });
  await page.screenshot({ path: screenshotPath, fullPage: true });
} finally {
  await browser.close();
}

console.log(`Browser smoke passed: ${screenshotPath}`);
