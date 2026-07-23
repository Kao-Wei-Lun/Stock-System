import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import { dashboardApi } from "../../api/dashboardApi";
import { getOperationalMetricsHistory } from "../../api/operationalMetricsApi";
import SystemHealthPanel from "./SystemHealthPanel.vue";

vi.mock("../../api/dashboardApi", () => ({
  dashboardApi: {
    getSystemDataQuality: vi.fn(),
  },
}));
vi.mock("../../api/operationalMetricsApi", () => ({
  getOperationalMetricsHistory: vi.fn(),
}));

function snapshot() {
  return {
    status: "warning",
    generated_at: "2026-07-22T04:00:00+00:00",
    summary: {
      healthy_count: 4,
      idle_count: 1,
      warning_count: 2,
      error_count: 0,
    },
    issues: [
      { component: "watchlist", status: "warning", message: "觀察池存在過期或缺少行情" },
    ],
    components: {
      database: { status: "healthy", label: "MySQL 可用", connected: true, latency_ms: 1.5 },
      backups: {
        status: "healthy", label: "資料庫備份在有效期限內", scope: "critical",
        created_at: "2026-07-22T01:00:00+00:00", age_hours: 3, size_bytes: 1048576,
      },
      watchlist: {
        status: "warning",
        label: "觀察池存在過期或缺少行情",
        ticker_count: 2,
        current_count: 1,
        stale_count: 1,
        stale_items: [{ ticker: "AAPL", is_stale: true, data_timestamp: "2026-07-01T00:00:00+00:00" }],
      },
    },
  };
}

describe("SystemHealthPanel", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the unified health snapshot and stale symbols", async () => {
    dashboardApi.getSystemDataQuality.mockResolvedValue(snapshot());
    getOperationalMetricsHistory.mockResolvedValue({
      point_count: 2,
      points: [
        {
          api: { p95_ms: 12 },
          database: { wait_p95_ms: 2 },
          realtime: { broadcast_p95_ms: 4 },
          freshness: { stale_ticker_count: 3 },
        },
        {
          api: { p95_ms: 8 },
          database: { wait_p95_ms: 1 },
          realtime: { broadcast_p95_ms: 3 },
          freshness: { stale_ticker_count: 1 },
        },
      ],
    });

    const wrapper = mount(SystemHealthPanel);
    await flushPromises();

    expect(wrapper.text()).toContain("系統與資料品質");
    expect(wrapper.text()).toContain("需注意");
    expect(wrapper.text()).toContain("觀察池行情");
    expect(wrapper.text()).toContain("重要資料");
    expect(wrapper.text()).toContain("1.00 MB");
    expect(wrapper.text()).toContain("AAPL · 已過期");
    expect(wrapper.text()).toContain("最近 24 小時");
    expect(wrapper.text()).toContain("API P95");
    expect(wrapper.text()).toContain("8.0 ms");
    expect(wrapper.findAll(".trend-card")).toHaveLength(4);
    expect(dashboardApi.getSystemDataQuality).toHaveBeenCalledTimes(1);
    expect(getOperationalMetricsHistory).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("allows a manual refresh and keeps errors visible", async () => {
    dashboardApi.getSystemDataQuality
      .mockResolvedValueOnce(snapshot())
      .mockRejectedValueOnce(new Error("後端暫時無法連線"));
    getOperationalMetricsHistory.mockResolvedValue({ point_count: 0, points: [] });

    const wrapper = mount(SystemHealthPanel);
    await flushPromises();
    await wrapper.get('[data-testid="refresh-health"]').trigger("click");
    await flushPromises();

    expect(dashboardApi.getSystemDataQuality).toHaveBeenCalledTimes(2);
    expect(wrapper.get('[role="alert"]').text()).toBe("後端暫時無法連線");
    wrapper.unmount();
  });

  it("keeps health visible when the optional trend history is unavailable", async () => {
    dashboardApi.getSystemDataQuality.mockResolvedValue(snapshot());
    getOperationalMetricsHistory.mockRejectedValue(new Error("趨勢暫時不可用"));

    const wrapper = mount(SystemHealthPanel);
    await flushPromises();

    expect(wrapper.text()).toContain("MySQL 可用");
    expect(wrapper.get('[data-testid="history-error"]').text()).toBe("趨勢暫時不可用");
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    wrapper.unmount();
  });
});
