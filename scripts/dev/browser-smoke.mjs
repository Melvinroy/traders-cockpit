import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const smokeLabel = (process.env.BROWSER_SMOKE_LABEL || "browser-smoke")
  .toLowerCase()
  .replace(/[^a-z0-9-_]+/g, "-");
const outputDir = path.resolve(process.cwd(), "output", "playwright");
const screenshotPath = path.join(outputDir, `${smokeLabel}.png`);
const consolePath = path.join(outputDir, `${smokeLabel}.console.txt`);
const networkPath = path.join(outputDir, `${smokeLabel}.network.txt`);
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [process.cwd(), path.resolve(process.cwd(), "frontend")]
});
const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
const { chromium } = playwrightModule.default ?? playwrightModule;

const consoleMessages = [];
const requestLog = [];
const requestFailures = [];
const pageErrors = [];
const authUsername = process.env.QC_AUTH_USERNAME || "admin";
const authPassword = process.env.QC_AUTH_PASSWORD || "change-me-admin";

function isRelevantFailure(url) {
  return !url.includes("/_next/webpack-hmr") && !url.includes("/api/auth/me");
}

async function launchBrowser() {
  try {
    return await chromium.launch({ channel: "chrome", headless: true });
  } catch {
    return chromium.launch({ headless: true });
  }
}

async function loginIfNeeded(page) {
  const loginTitle = page.getByText("Session Required");
  if ((await loginTitle.count()) === 0) return false;
  await page.getByLabel("Username").fill(authUsername);
  await page.getByLabel("Password").fill(authPassword);
  await page.getByRole("button", { name: "SIGN IN" }).click();
  await page.getByText("Setup Parameters").waitFor({ timeout: 15000 });
  return true;
}

const browser = await launchBrowser();
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } });

page.on("console", (message) => {
  const entry = `[${message.type().toUpperCase()}] ${message.text()}`;
  consoleMessages.push(entry);
});

page.on("pageerror", (error) => {
  pageErrors.push(error.message);
});

page.on("response", async (response) => {
  const entry = `[${response.request().method()}] ${response.url()} => [${response.status()}] ${response.statusText()}`;
  requestLog.push(entry);
  if (response.status() >= 400 && isRelevantFailure(response.url())) {
    requestFailures.push(entry);
  }
});

page.on("requestfailed", (request) => {
  const failure = request.failure();
  const entry = `[${request.method()}] ${request.url()} => [FAILED] ${failure?.errorText ?? "request failed"}`;
  requestLog.push(entry);
  if (isRelevantFailure(request.url())) {
    requestFailures.push(entry);
  }
});

try {
  await fs.mkdir(outputDir, { recursive: true });

  const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load cleanly at ${frontendUrl}.`);
  }

  const title = await page.title();
  if (!title.includes("Trader's Cockpit")) {
    throw new Error(`Unexpected page title: ${title}`);
  }

  const loggedIn = await loginIfNeeded(page);
  if (loggedIn) {
    consoleMessages.length = 0;
    requestLog.length = 0;
    requestFailures.length = 0;
    pageErrors.length = 0;
  }
  await page.getByRole("button", { name: /LOAD SETUP/ }).click();
  await page.getByText("SETUP LOADED").waitFor({ timeout: 15000 });
  await page.getByText("Suggested Entry").waitFor({ timeout: 15000 });
  await page.getByText("Stop Plan").waitFor({ timeout: 15000 });
  await page.getByText("Profit Taking").waitFor({ timeout: 15000 });
  await page.getByText("Activity Log").waitFor({ timeout: 15000 });
  await page.screenshot({ path: screenshotPath, fullPage: true });

  await fs.writeFile(consolePath, `${consoleMessages.join("\n")}\n`, "utf8");
  await fs.writeFile(networkPath, `${requestLog.join("\n")}\n`, "utf8");

  const consoleErrors = consoleMessages.filter(
    (entry) => entry.startsWith("[ERROR]") && !entry.includes("401 (Unauthorized)")
  );
  if (pageErrors.length || consoleErrors.length || requestFailures.length) {
    const details = [
      pageErrors.length ? `Page errors:\n${pageErrors.join("\n")}` : "",
      consoleErrors.length ? `Console errors:\n${consoleErrors.join("\n")}` : "",
      requestFailures.length ? `Request failures:\n${requestFailures.join("\n")}` : ""
    ]
      .filter(Boolean)
      .join("\n\n");
    throw new Error(`Browser smoke failed for ${frontendUrl}\n\n${details}`);
  }
} finally {
  await browser.close();
}

console.log(`Browser smoke passed: ${screenshotPath}`);
