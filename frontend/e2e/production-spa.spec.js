import { expect, test } from "@playwright/test";

const primaryRoutes = [
  { label: "總覽", path: "/app/overview/2330.TW", marker: "QuantVision" },
  { label: "終端", path: "/app/terminal/%2ATMFF", marker: "Pro Chart Terminal" },
  { label: "籌碼", path: "/app/institutional/2330.TW", marker: "把法人動向" },
  { label: "復盤", path: "/app/review/journal/2330.TW", marker: "把盤中的決策痕跡" },
  { label: "資產", path: "/app/assets/2330.TW", marker: "個人資產總覽" },
  { label: "設定", path: "/app/settings/2330.TW", marker: "系統設定" },
];

async function resetFixture(request, patch = {}) {
  await request.post("/api/e2e/control", {
    data: {
      ohlc_delay_ms: 0,
      realtime_delay_ms: 600,
      ready_status: "ready",
      ...patch,
    },
  });
}

function routeMarker(page, route) {
  if (route.label === "終端") return page.locator(".terminal-kicker");
  return page.getByRole("heading", { name: new RegExp(route.marker) }).first();
}

test.beforeEach(async ({ request }) => {
  await resetFixture(request);
});

test("production SPA serves deep links while API and missing assets never fall back to index", async ({ request }) => {
  for (const route of primaryRoutes) {
    const response = await request.get(route.path);
    expect(response.ok(), route.path).toBe(true);
    expect(response.headers()["cache-control"]).toBe("no-cache");
    expect(await response.text()).toContain('<div id="app"></div>');
  }

  const apiResponse = await request.get("/api/not-a-real-production-route");
  expect(apiResponse.headers()["content-type"]).toContain("application/json");
  expect(await apiResponse.text()).not.toContain('<div id="app"></div>');

  const missingAsset = await request.get("/app/assets/missing-e2e-chunk.js");
  expect(missingAsset.status()).toBe(404);
  expect(await missingAsset.text()).not.toContain('<div id="app"></div>');
});

test("all primary navigation and direct reload routes remain usable", async ({ page }) => {
  await page.goto("/app/overview/2330.TW");
  await expect(page.getByRole("button", { name: /QuantVision/ })).toBeVisible();

  for (const route of primaryRoutes.slice(1)) {
    await page.getByRole("button", { name: new RegExp(`^${route.label}`) }).click();
    const routePrefix = route.path.split("/").slice(0, 3).join("/");
    await expect(page).toHaveURL(new RegExp(`${routePrefix}/`, "i"));
    await expect(routeMarker(page, route)).toBeVisible();
    await page.reload();
    await expect(page.locator('[data-testid="frontend-recovery"]')).toHaveCount(0);
    await expect(routeMarker(page, route)).toBeVisible();
  }

  await page.getByRole("button", { name: /^模擬/ }).click();
  await expect(page).toHaveURL(/\/app\/paper-trading$/);
  await expect(page.getByText("本頁不會送出任何真實委託")).toBeVisible();
});

test("dynamic futures aliases resolve, cache confirms against DB, realtime updates, and Y scale is explicit", async ({
  page,
  request,
}) => {
  await page.goto("/app/terminal/%2ATMFF");
  await expect(page.getByRole("heading", { name: "TMFH7" })).toBeVisible();
  await expect(page.getByText("資料庫資料", { exact: true })).toBeVisible();

  const search = page.getByPlaceholder("搜尋代號或名稱...");
  await search.fill("*TXFF");
  await expect(page.getByText("E2E 期貨（目前 TXFH7）")).toBeVisible();
  await page.getByText("E2E 期貨（目前 TXFH7）").click();
  await expect(page.getByRole("heading", { name: "TXFH7" })).toBeVisible();

  const menu = page.locator(".toolbar-menu").filter({ hasText: "更多" }).first();
  await menu.hover();
  await page.getByRole("button", { name: "Y＋" }).click();
  await expect(page.locator(".y-scale-chip")).toContainText("手動鎖定");
  await menu.hover();
  await page.getByRole("button", { name: "Y 自動" }).click();
  await expect(page.locator(".y-scale-chip")).toContainText("Y 軸 自動");

  await page.evaluate(async () => {
    const payload = await fetch("/api/futopt/ohlc/TXFH7?period=1d&interval=1m").then((response) => response.json());
    const database = await new Promise((resolve, reject) => {
      const request = indexedDB.open("quantvision-terminal-cache", 1);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    await new Promise((resolve, reject) => {
      const transaction = database.transaction("snapshots", "readwrite");
      const store = transaction.objectStore("snapshots");
      for (const ticker of ["TXFH7", "*TXFF"]) {
        store.put({
          key: `${ticker}::1m`,
          schemaVersion: 1,
          ticker,
          interval: "1m",
          savedAt: Date.now(),
          latestCandleTime: payload.data.at(-1).date,
          rows: payload.data,
        });
      }
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    database.close();
  });
  await resetFixture(request, { ohlc_delay_ms: 1800, realtime_delay_ms: 3200 });
  await page.reload();
  await expect(page.getByText("快取資料", { exact: true })).toBeVisible();
  await expect(page.getByText("資料庫資料", { exact: true })).toBeVisible({ timeout: 5_000 });
  await expect(page.getByText("即時更新", { exact: true })).toBeVisible({ timeout: 7_000 });
});

test("WebSocket disconnect shows reconnect state and recovers without a page restart", async ({ page, request }) => {
  await page.goto("/app/terminal/%2ATMFF");
  const socketStatus = page.locator('[title="WebSocket 狀態"]');
  await expect(socketStatus).toHaveClass(/live/);

  await request.post("/api/e2e/ws/drop");
  await expect(socketStatus).toHaveClass(/warn/);
  await expect(socketStatus).toHaveClass(/live/, { timeout: 9_000 });
});

test("paper and asset pages use synthetic data, while chunk failures expose recovery controls", async ({ page }) => {
  await page.goto("/app/assets/2330.TW");
  await page.getByRole("button", { name: "資料維護" }).click();
  await expect(page.locator("option", { hasText: "E2E 合成資產帳戶" }).first()).toHaveText("E2E 合成資產帳戶");

  let rejectedChunks = 0;
  await page.route(/\/app\/assets\/PaperTradingView-.*\.js$/, async (route) => {
    rejectedChunks += 1;
    await route.abort("failed");
  });
  await page.getByRole("button", { name: /^模擬/ }).click();
  await expect(page.locator('[data-testid="frontend-recovery"]')).toBeVisible();
  expect(rejectedChunks).toBeGreaterThanOrEqual(1);
  await page.unroute(/\/app\/assets\/PaperTradingView-.*\.js$/);

  await page.getByRole("button", { name: "重新載入模組" }).click();
  await expect(page.getByText("本頁不會送出任何真實委託")).toBeVisible();
  await expect(page.getByText("E2E TMF 模擬帳戶")).toBeVisible();
});

test("readiness fixture covers starting, degraded, ready, and unavailable responses", async ({ request }) => {
  for (const status of ["starting", "ready_degraded", "ready"]) {
    await resetFixture(request, { ready_status: status });
    const response = await request.get("/api/ready");
    expect(response.ok()).toBe(true);
    expect((await response.json()).status).toBe(status);
  }

  const unavailable = await request.get("http://127.0.0.1:1/api/ready", {
    timeout: 1_000,
    failOnStatusCode: false,
  }).catch((error) => error);
  expect(unavailable).toBeInstanceOf(Error);
});
