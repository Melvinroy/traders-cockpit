import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010";
const smokeLabel = (process.env.BROWSER_SMOKE_LABEL || "browser-smoke")
  .toLowerCase()
  .replace(/[^a-z0-9-_]+/g, "-");
const qcSymbol = (process.env.QC_SYMBOL || "MSFT").trim().toUpperCase() || "MSFT";
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

async function seedAuthSession(page) {
  const response = await fetch(`${backendUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: authUsername, password: authPassword }),
  });
  if (!response.ok) {
    throw new Error(`Unable to authenticate against ${backendUrl} for browser smoke.`);
  }
  const rawCookie = response.headers.get("set-cookie");
  if (!rawCookie) {
    throw new Error("Missing auth cookie from backend login.");
  }
  const [cookiePair] = rawCookie.split(";");
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

async function ensureCockpitReady(page) {
  const setupParameters = page.getByText("Setup Parameters");
  const loginTitle = page.getByText("Session Required");
  await Promise.race([
    setupParameters.waitFor({ timeout: 15000 }),
    loginTitle.waitFor({ timeout: 15000 }),
  ]);
  const loggedIn = await loginIfNeeded(page);
  if (!loggedIn) {
    await setupParameters.waitFor({ timeout: 15000 });
  }
  return loggedIn;
}

async function loadSetup(page) {
  const symbolInput = page.locator("#tickerInput");
  await symbolInput.waitFor({ state: "visible", timeout: 15000 });
  await symbolInput.fill(qcSymbol);
  await page.waitForFunction(
    (value) => {
      const input = document.querySelector("#tickerInput");
      return input instanceof HTMLInputElement && input.value === value;
    },
    qcSymbol,
    { timeout: 5000 }
  );
  await symbolInput.press("Enter");
  await page.waitForTimeout(800);
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
  await seedAuthSession(page);

  const response = await page.goto(frontendUrl, { waitUntil: "load" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load cleanly at ${frontendUrl}.`);
  }

  const title = await page.title();
  if (!title.includes("Trader's Cockpit")) {
    throw new Error(`Unexpected page title: ${title}`);
  }

  const loggedIn = await ensureCockpitReady(page);
  if (loggedIn) {
    consoleMessages.length = 0;
    requestLog.length = 0;
    requestFailures.length = 0;
    pageErrors.length = 0;
  }
  await loadSetup(page);
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
