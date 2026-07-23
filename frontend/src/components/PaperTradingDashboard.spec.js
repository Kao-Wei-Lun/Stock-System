import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import PaperTradingDashboard from "./PaperTradingDashboard.vue";

function jsonResponse(payload, { ok = true, status = 200 } = {}) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(payload),
  });
}

function mountDashboard() {
  return mount(PaperTradingDashboard, {
    global: {
      mocks: { $router: { push: vi.fn() } },
      stubs: { FuturesRiskSizerPanel: true },
    },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("PaperTradingDashboard resilient loading", () => {
  it("loads persisted sections without automatically calling the margin provider", async () => {
    const requests = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      requests.push(String(url));
      if (String(url).endsWith("/accounts")) {
        return jsonResponse({
          items: [{
            id: 4,
            name: "TMF 模擬帳戶",
            product_symbol: "TMF",
            initial_margin_per_contract: 28900,
            margin_last_success_at: "2026-07-22 09:00:00",
            risk_config: {},
          }],
        });
      }
      if (String(url).endsWith("/bots")) return jsonResponse({ items: [] });
      if (String(url).endsWith("/replay/runs")) return jsonResponse({ items: [] });
      if (String(url).endsWith("/risk/position-size")) {
        return jsonResponse({ sizing: { addable_contracts: 1, limiting_factor: "margin" } });
      }
      return jsonResponse({});
    }));

    const wrapper = mountDashboard();
    await flushPromises();

    expect(wrapper.get('[data-testid="simulation-safety-notice"]').text()).toContain("不會送出任何真實委託");
    expect(wrapper.get('[data-paper-section="accounts"]').exists()).toBe(true);
    expect(wrapper.get('[data-testid="margin-fallback"]').text()).toContain("資料庫保存值");
    expect(requests.some((url) => url.endsWith("/accounts/margin/estimate"))).toBe(false);
    expect(wrapper.text()).toContain("最後成功");
    expect(wrapper.text()).toContain("28,900");
    wrapper.unmount();
  });

  it("shows an actionable account loading error instead of swallowing it", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).endsWith("/accounts")) {
        return jsonResponse({ detail: "database unavailable" }, { ok: false, status: 503 });
      }
      if (String(url).endsWith("/bots") || String(url).endsWith("/replay/runs")) {
        return jsonResponse({ items: [] });
      }
      return jsonResponse({ sizing: {} });
    }));

    const wrapper = mountDashboard();
    await flushPromises();

    expect(wrapper.get('[data-testid="accounts-error"]').text()).toContain("database unavailable");
    expect(wrapper.get('[data-testid="accounts-error"] button').text()).toBe("重試");
    wrapper.unmount();
  });

  it("keeps replay history visible when the margin provider is degraded", async () => {
    let failMargin = false;
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).endsWith("/accounts")) {
        return jsonResponse({
          items: [{
            id: 4,
            name: "TMF 模擬帳戶",
            product_symbol: "TMF",
            initial_margin_per_contract: 28900,
            risk_config: {},
          }],
        });
      }
      if (String(url).endsWith("/bots")) return jsonResponse({ items: [] });
      if (String(url).endsWith("/replay/runs")) {
        return jsonResponse({
          items: [{
            id: 12,
            start_date: "2026-07-01",
            end_date: "2026-07-02",
            trade_count: 3,
            total_return_pct: 1.2,
            max_drawdown_pct: 0.4,
            win_rate_pct: 66.7,
          }],
        });
      }
      if (String(url).endsWith("/accounts/margin/estimate") && failMargin) {
        return jsonResponse({ detail: "provider disconnected" }, { ok: false, status: 503 });
      }
      return jsonResponse({ sizing: {} });
    }));

    const wrapper = mountDashboard();
    await flushPromises();
    failMargin = true;
    const marginButton = wrapper.findAll("button").find((button) => button.text().includes("預查保證金"));
    await marginButton.trigger("click");
    await flushPromises();

    expect(wrapper.get('[data-testid="margin-error"]').text()).toContain("provider disconnected");
    await wrapper.findAll(".pt-tab").find((tab) => tab.text().includes("歷史回放")).trigger("click");
    expect(wrapper.text()).toContain("2026-07-01 ~ 2026-07-02");
    wrapper.unmount();
  });
});
