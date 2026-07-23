import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import FrontendErrorBoundary from "./FrontendErrorBoundary.vue";
import { reportFrontendError } from "../utils/frontendRecovery";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FrontendErrorBoundary", () => {
  it("shows accessible recovery actions for a dynamic import failure", async () => {
    const wrapper = mount(FrontendErrorBoundary, {
      slots: { default: "<div data-testid='workspace'>workspace</div>" },
    });

    reportFrontendError(
      new TypeError("Failed to fetch dynamically imported module: /app/chunk.js"),
      "route-module",
    );
    await wrapper.vm.$nextTick();

    const recovery = wrapper.get('[data-testid="frontend-recovery"]');
    expect(recovery.attributes("role")).toBe("alert");
    expect(recovery.text()).toContain("錯誤分類：module_load");
    expect(recovery.text()).toContain("清除前端快取並重載");

    await recovery.get("button").trigger("click");
    expect(wrapper.find('[data-testid="frontend-recovery"]').exists()).toBe(false);
    expect(wrapper.get('[data-testid="workspace"]').text()).toBe("workspace");
    wrapper.unmount();
  });
});
