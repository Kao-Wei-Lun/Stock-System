import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

vi.mock("./AppShellRouteView.vue", () => ({
  default: {
    name: "AppShellRouteView",
    props: ["workspaceTab", "rightTab"],
    template: `<div data-testid="app-shell-route">{{ workspaceTab }}|{{ rightTab }}</div>`,
  },
}));

import DashboardView from "./DashboardView.vue";

describe("DashboardView", () => {
  it("keeps the legacy dashboard view pointed at the terminal workspace", () => {
    const wrapper = mount(DashboardView);

    expect(wrapper.get('[data-testid="app-shell-route"]').text()).toBe("terminal|alerts");
  });
});
