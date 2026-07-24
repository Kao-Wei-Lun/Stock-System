import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationPanel from "./NotificationPanel.vue";
import {
  NOTIFICATION_LAYOUT_STORAGE_KEY,
  saveNotificationLayout,
} from "../utils/floatingPanelLayout";

const desktopWidth = window.innerWidth;
const desktopHeight = window.innerHeight;
const originalResizeObserver = globalThis.ResizeObserver;

function storedLayout() {
  return JSON.parse(window.localStorage.getItem(NOTIFICATION_LAYOUT_STORAGE_KEY));
}

async function mountOpenPanel() {
  const wrapper = mount(NotificationPanel, {
    props: { notifications: [] },
  });
  if (wrapper.find('[data-testid="notif-center-toggle"]').exists()) {
    await wrapper.get('[data-testid="notif-center-toggle"]').trigger("click");
  }
  return wrapper;
}

describe("NotificationPanel floating layout", () => {
  beforeEach(() => {
    window.localStorage.removeItem(NOTIFICATION_LAYOUT_STORAGE_KEY);
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: desktopWidth,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: desktopHeight,
    });
  });

  afterEach(() => {
    window.localStorage.removeItem(NOTIFICATION_LAYOUT_STORAGE_KEY);
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: desktopWidth,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: desktopHeight,
    });
    globalThis.ResizeObserver = originalResizeObserver;
    vi.restoreAllMocks();
  });

  it("docks, persists, restores, and resets the chosen position", async () => {
    const first = await mountOpenPanel();

    await first.get('[data-testid="notif-dock-top-left"]').trigger("click");
    expect(first.classes()).toContain("is-top-left");
    expect(storedLayout()).toMatchObject({
      anchor: "top-left",
      collapsed: false,
    });
    first.unmount();

    const restored = mount(NotificationPanel, {
      props: { notifications: [] },
    });
    expect(restored.find('[data-testid="notif-center-panel"]').exists()).toBe(true);
    expect(restored.classes()).toContain("is-top-left");

    await restored.get('[data-testid="notif-layout-reset"]').trigger("click");
    expect(restored.classes()).toContain("is-bottom-right");
    expect(storedLayout()).toMatchObject({
      anchor: "bottom-right",
      collapsed: false,
    });
  });

  it("supports pointer dragging and keyboard position adjustments", async () => {
    const wrapper = await mountOpenPanel();
    const shell = wrapper.get(".notif-center-shell");
    vi.spyOn(shell.element, "getBoundingClientRect").mockReturnValue({
      x: 640,
      y: 200,
      top: 200,
      right: 1000,
      bottom: 700,
      left: 640,
      width: 360,
      height: 500,
      toJSON: () => ({}),
    });

    const handle = wrapper.get('[data-testid="notif-drag-handle"]');
    await handle.trigger("pointerdown", {
      button: 0,
      pointerId: 7,
      clientX: 660,
      clientY: 220,
    });
    await handle.trigger("pointermove", {
      pointerId: 7,
      clientX: 500,
      clientY: 250,
    });
    await handle.trigger("pointerup", { pointerId: 7 });

    expect(wrapper.classes()).toContain("is-custom");
    expect(wrapper.attributes("style")).toContain("left: 480px");
    expect(wrapper.attributes("style")).toContain("top: 230px");
    expect(storedLayout()).toMatchObject({
      anchor: "custom",
      x: 480,
      y: 230,
    });

    await handle.trigger("keydown", { key: "ArrowLeft" });
    expect(storedLayout()).toMatchObject({
      anchor: "custom",
      x: 470,
      y: 230,
    });
  });

  it("clamps a restored custom position after the viewport changes", async () => {
    saveNotificationLayout({
      version: 1,
      anchor: "custom",
      x: 900,
      y: 700,
      panelHeight: 500,
      collapsed: false,
    });
    const wrapper = mount(NotificationPanel, {
      props: { notifications: [] },
    });
    const shell = wrapper.get(".notif-center-shell");
    vi.spyOn(shell.element, "getBoundingClientRect").mockReturnValue({
      x: 900,
      y: 700,
      top: 700,
      right: 1260,
      bottom: 1200,
      left: 900,
      width: 360,
      height: 500,
      toJSON: () => ({}),
    });

    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 1000,
    });
    Object.defineProperty(window, "innerHeight", {
      configurable: true,
      value: 700,
    });
    window.dispatchEvent(new Event("resize"));
    await wrapper.vm.$nextTick();

    expect(storedLayout()).toMatchObject({
      anchor: "custom",
      x: 622,
      y: 182,
    });
  });

  it("persists a user-resized desktop panel height", async () => {
    let resizeCallback = null;
    globalThis.ResizeObserver = class {
      constructor(callback) {
        resizeCallback = callback;
      }

      observe() {}

      disconnect() {}
    };

    const wrapper = await mountOpenPanel();
    await wrapper.vm.$nextTick();
    expect(resizeCallback).toBeTypeOf("function");

    resizeCallback([{ contentRect: { height: 430 } }]);
    await wrapper.vm.$nextTick();
    expect(storedLayout()).toMatchObject({
      panelHeight: 430,
      collapsed: false,
    });
  });

  it("uses the fixed mobile drawer layout and ignores desktop docking controls", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 390,
    });
    const wrapper = await mountOpenPanel();

    expect(wrapper.classes()).toContain("is-compact");
    await wrapper.get('[data-testid="notif-dock-top-left"]').trigger("click");
    expect(storedLayout()).toMatchObject({
      anchor: "bottom-right",
      collapsed: false,
    });
    expect(wrapper.classes()).not.toContain("is-top-left");
  });
});
