import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "@playwright/test";

const frontendDir = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(frontendDir, "..");
const fixturePort = Number(process.env.QV_E2E_PORT || 4174);
const fixtureHost = "127.0.0.1";
const baseURL = `http://${fixtureHost}:${fixturePort}`;
const defaultPython = path.join(repositoryRoot, "venv", "Scripts", "python.exe");
const python = process.env.QV_E2E_PYTHON || defaultPython;
const fixtureScript = path.join(repositoryRoot, "scripts", "e2e_fixture_server.py");

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  forbidOnly: true,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["line"]],
  timeout: 30_000,
  expect: {
    timeout: 8_000,
  },
  use: {
    baseURL,
    channel: process.env.QV_E2E_BROWSER_CHANNEL || "chrome",
    headless: true,
    viewport: { width: 1600, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${python}" -X utf8 "${fixtureScript}" --host ${fixtureHost} --port ${fixturePort}`,
    cwd: repositoryRoot,
    url: `${baseURL}/api/ready`,
    reuseExistingServer: false,
    timeout: 60_000,
    stdout: "ignore",
    stderr: "pipe",
  },
});
