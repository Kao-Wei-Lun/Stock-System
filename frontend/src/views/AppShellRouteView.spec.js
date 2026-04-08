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
            @click="$emit('route-change', { workspaceTab: 'terminal', rightTab: 'alerts', currentTicker: routeTicker })"
          />
          <button
            data-testid="emit-review-route"
            @click="$emit('route-change', { workspaceTab: 'review', rightTab: 'backtest', currentTicker: 'msft' })"
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
    routeState.name = "terminal";
    routeState.params = { ticker: "aapl" };
    replace.mockReset();
  });

  it("normalizes the route ticker before passing it into the app shell", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "terminal",
        rightTab: "alerts",
      },
    });

    await flushPromises();

    expect(wrapper.get('[data-testid="route-props"]').text()).toBe("terminal|alerts|AAPL");
  });

  it("does not replace the route when the target route is already active", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "terminal",
        rightTab: "alerts",
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="emit-same-route"]').trigger("click");

    expect(replace).not.toHaveBeenCalled();
  });

  it("replaces the route when the app shell requests a different view", async () => {
    const wrapper = mount(AppShellRouteView, {
      props: {
        workspaceTab: "terminal",
        rightTab: "alerts",
      },
    });

    await flushPromises();
    await wrapper.get('[data-testid="emit-review-route"]').trigger("click");

    expect(replace).toHaveBeenCalledWith({
      name: "backtest",
      params: { ticker: "MSFT" },
    });
  });
});
