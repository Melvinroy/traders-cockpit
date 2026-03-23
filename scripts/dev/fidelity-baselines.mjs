import fs from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const frontendUrl = process.env.FRONTEND_URL || "http://127.0.0.1:3010";
const backendUrl = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010";
const outputDir = path.resolve(process.cwd(), "output", "playwright");
const qcSymbol = (process.env.QC_SYMBOL || "MSFT").trim().toUpperCase() || "MSFT";
const require = createRequire(import.meta.url);
const playwrightEntry = require.resolve("playwright", {
  paths: [process.cwd(), path.resolve(process.cwd(), "frontend")]
});
const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
const { chromium } = playwrightModule.default ?? playwrightModule;
const authUsername = process.env.QC_AUTH_USERNAME || "admin";
const authPassword = process.env.QC_AUTH_PASSWORD || "change-me-admin";

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

async function loginIfNeeded(page) {
  const loginTitle = page.getByText("Session Required");
  if ((await loginTitle.count()) === 0) return;
  await page.getByLabel("Username").fill(authUsername);
  await page.getByLabel("Password").fill(authPassword);
  await page.getByRole("button", { name: "SIGN IN" }).click();
  await page.getByText("Setup Parameters").waitFor({ timeout: 15000 });
}

async function seedAuthSession(page) {
  const response = await fetch(`${backendUrl}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: authUsername, password: authPassword }),
  });
  if (!response.ok) {
    throw new Error(`Unable to authenticate against ${backendUrl} for baseline capture.`);
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
  await loginIfNeeded(page);
  await setupParameters.waitFor({ timeout: 15000 });
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

try {
  await fs.mkdir(outputDir, { recursive: true });
  await seedAuthSession(page);

  const response = await page.goto(frontendUrl, { waitUntil: "networkidle" });
  if (!response || response.status() >= 400) {
    throw new Error(`Frontend root failed to load for baseline capture at ${frontendUrl}.`);
  }
  await ensureCockpitReady(page);

  const resetButton = page.getByRole("button", { name: "RESET" });
  if ((await resetButton.count()) > 0) {
    await resetButton.click();
  }
  await page.getByText("IDLE").waitFor({ timeout: 10000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-idle.png"), fullPage: true });

  await ensureCockpitReady(page);
  await loadSetup(page);
  await page.getByText("SETUP LOADED").waitFor({ timeout: 15000 });
  await page.screenshot({ path: path.join(outputDir, "baseline-setup-loaded.png"), fullPage: true });

  await page.reload({ waitUntil: "networkidle" });
  await ensureCockpitReady(page);
  await page.waitForTimeout(1500);
  const phaseText = (await page.locator(".state-display").textContent())?.trim() || "unknown";
  await page.screenshot({ path: path.join(outputDir, `baseline-${safeName(phaseText)}.png`), fullPage: true });
} finally {
  await browser.close();
}

console.log(`Fidelity baselines captured in ${outputDir}`);
