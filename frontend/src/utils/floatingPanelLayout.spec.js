import { describe, expect, it, vi } from "vitest";

import {
  DEFAULT_NOTIFICATION_LAYOUT,
  NOTIFICATION_LAYOUT_STORAGE_KEY,
  anchorClassName,
  clampFloatingPanelPosition,
  clearNotificationLayout,
  loadNotificationLayout,
  normalizeNotificationLayout,
  saveNotificationLayout,
} from "./floatingPanelLayout";

function memoryStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem: vi.fn((key) => values.get(key) ?? null),
    setItem: vi.fn((key, value) => values.set(key, value)),
    removeItem: vi.fn((key) => values.delete(key)),
    values,
  };
}

describe("floating notification layout", () => {
  it("normalizes invalid persisted values to safe defaults", () => {
    expect(normalizeNotificationLayout(null)).toEqual(DEFAULT_NOTIFICATION_LAYOUT);
    expect(normalizeNotificationLayout({ version: 0, anchor: "custom" })).toEqual(DEFAULT_NOTIFICATION_LAYOUT);
    expect(normalizeNotificationLayout({
      version: 1,
      anchor: "custom",
      x: "bad",
      y: 20,
      panelHeight: 9999,
      collapsed: false,
    })).toEqual({
      ...DEFAULT_NOTIFICATION_LAYOUT,
      panelHeight: 680,
      collapsed: false,
    });
  });

  it("clamps custom coordinates and panel height", () => {
    expect(normalizeNotificationLayout({
      version: 1,
      anchor: "custom",
      x: -40,
      y: 42.4,
      panelHeight: 120,
      collapsed: false,
    })).toEqual({
      version: 1,
      anchor: "custom",
      x: 0,
      y: 42,
      panelHeight: 240,
      collapsed: false,
    });

    expect(clampFloatingPanelPosition(
      { x: 1200, y: -50 },
      {
        panelWidth: 360,
        panelHeight: 500,
        viewportWidth: 1280,
        viewportHeight: 720,
        margin: 18,
      },
    )).toEqual({ x: 902, y: 18 });
  });

  it("loads, saves, clears, and tolerates blocked storage", () => {
    const storage = memoryStorage();
    const saved = saveNotificationLayout({
      version: 1,
      anchor: "top-left",
      collapsed: false,
    }, storage);

    expect(saved.anchor).toBe("top-left");
    expect(loadNotificationLayout(storage).anchor).toBe("top-left");
    clearNotificationLayout(storage);
    expect(storage.values.has(NOTIFICATION_LAYOUT_STORAGE_KEY)).toBe(false);

    const blocked = {
      getItem: () => { throw new Error("blocked"); },
      setItem: () => { throw new Error("blocked"); },
      removeItem: () => { throw new Error("blocked"); },
    };
    expect(loadNotificationLayout(blocked)).toEqual(DEFAULT_NOTIFICATION_LAYOUT);
    expect(() => saveNotificationLayout(DEFAULT_NOTIFICATION_LAYOUT, blocked)).not.toThrow();
    expect(() => clearNotificationLayout(blocked)).not.toThrow();
  });

  it("maps anchors to stable CSS classes", () => {
    expect(anchorClassName("top-left")).toBe("is-top-left");
    expect(anchorClassName("bottom-right")).toBe("is-bottom-right");
    expect(anchorClassName("unexpected")).toBe("is-custom");
  });
});
