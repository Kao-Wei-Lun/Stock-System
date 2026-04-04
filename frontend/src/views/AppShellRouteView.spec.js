import { flushPromises, mount } from "@vue/test-utils";
import { reactive } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("vue", async () => {
  const actual = await vi.importActual("vue");
  return {
    ...actual,
    defineAsyncComponent: () => ({
      name: "AppShellMock",
      props: ["routeWorkspaceTab", "routeRightTab", "routeTicker"],
      template: `
        <div>
          <div data-testid="route-props">{{ routeWorkspaceTab }}|{{ routeRightTab }}|{{ routeTicker }}</div>
          <button
            data-testid="emit-same-route"
            @click="$emit('route-change', { workspaceTab: 'chart', rightTab: 'indicators', currentTicker: routeTicker })"
          />
          <button
            data-testid="emit-alert-route"
            @click="$emit('route-change', { workspaceTab: 'chart', rightTab: 'alerts', currentTicker: 'msft' })"
          />
        </div>
      `,
    }),
  };
});

const routeState = reactive({
  name: "dashboard",
  params: { ticker: "aapl" },
});

const replace = vi.fn();

vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace }),
}));

import AppShellRouteView from "./AppShellRouteView.vue";

describe("AppShellRouteView", () => {
  beforeEach(() => {
    routeState.name = "dashboard";
    routeState.params = { ticker: "aapl" };
    replace.mockReset();
  });

  it("normalizes the route ticker before passing it into the app shell", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "chart",
        rightTab: "indicators",
      },
    });

    await flushPromises();

    expect(wrapper.get('[data-testid="route-props"]').text()).toBe("chart|indicators|AAPL");
  });

  it("does not replace the route when the target route is already active", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "chart",
        rightTab: "indicators",
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="emit-same-route"]').trigger("click");

    expect(replace).not.toHaveBeenCalled();
  });

  it("replaces the route when the app shell requests a different view", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "chart",
        rightTab: "indicators",
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="emit-alert-route"]').trigger("click");

    expect(replace).toHaveBeenCalledWith({
      name: "alerts",
      params: { ticker: "MSFT" },
    });
  });
});
