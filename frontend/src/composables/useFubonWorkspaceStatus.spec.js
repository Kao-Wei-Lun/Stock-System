import { flushPromises, mount } from "@vue/test-utils";
import { defineComponent } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useFubonWorkspaceStatus } from "./useFubonWorkspaceStatus";

const Harness = defineComponent({
  template: "<div></div>",
  setup() {
    return useFubonWorkspaceStatus({ pollMs: 1_000 });
  },
});

function buildJsonResponse(payload) {
  return {
    ok: true,
    status: 200,
    headers: {
      get: () => "application/json",
    },
    json: async () => payload,
  };
}

describe("useFubonWorkspaceStatus", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("marks the badge connected when the active account is online", async () => {
    globalThis.fetch.mockResolvedValue(buildJsonResponse({
      accounts: [
        {
          id: 1,
          is_active: true,
          is_enabled: true,
          connection_status: "connected",
        },
      ],
    }));

    const wrapper = mount(Harness);
    await flushPromises();

    expect(wrapper.vm.fubonStatus).toBe("connected");
    expect(wrapper.vm.showFubonOnboardingBanner).toBe(false);
  });

  it("shows the onboarding banner and persists dismiss state when no account exists", async () => {
    globalThis.fetch.mockResolvedValue(buildJsonResponse({ accounts: [] }));

    const wrapper = mount(Harness);
    await flushPromises();

    expect(wrapper.vm.fubonStatus).toBe("unconfigured");
    expect(wrapper.vm.showFubonOnboardingBanner).toBe(true);

    wrapper.vm.dismissFubonOnboardingBanner();

    expect(wrapper.vm.showFubonOnboardingBanner).toBe(false);
    expect(window.localStorage.getItem("quantvision:fubon-onboarding-dismissed")).toBe("1");
  });

  it("polls the status endpoint on an interval", async () => {
    globalThis.fetch.mockResolvedValue(buildJsonResponse({ accounts: [] }));

    mount(Harness);
    await flushPromises();

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(1_000);
    await flushPromises();

    expect(globalThis.fetch).toHaveBeenCalledTimes(2);
  });
});
