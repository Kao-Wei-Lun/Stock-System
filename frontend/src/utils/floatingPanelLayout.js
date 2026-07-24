export const NOTIFICATION_LAYOUT_STORAGE_KEY = "quantvision:notification-center-layout:v1";
export const NOTIFICATION_LAYOUT_VERSION = 1;
export const NOTIFICATION_PANEL_MARGIN = 18;
export const NOTIFICATION_PANEL_MIN_HEIGHT = 240;
export const NOTIFICATION_PANEL_MAX_HEIGHT = 680;

export const NOTIFICATION_PANEL_ANCHORS = Object.freeze([
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
]);

const VALID_LAYOUT_MODES = new Set([...NOTIFICATION_PANEL_ANCHORS, "custom"]);

export const DEFAULT_NOTIFICATION_LAYOUT = Object.freeze({
  version: NOTIFICATION_LAYOUT_VERSION,
  anchor: "bottom-right",
  x: null,
  y: null,
  panelHeight: null,
  collapsed: true,
});

function finiteNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), Math.max(minimum, maximum));
}

export function normalizeNotificationLayout(value) {
  if (!value || typeof value !== "object" || Number(value.version) !== NOTIFICATION_LAYOUT_VERSION) {
    return { ...DEFAULT_NOTIFICATION_LAYOUT };
  }

  const anchor = VALID_LAYOUT_MODES.has(value.anchor)
    ? value.anchor
    : DEFAULT_NOTIFICATION_LAYOUT.anchor;
  const x = finiteNumber(value.x);
  const y = finiteNumber(value.y);
  const panelHeight = finiteNumber(value.panelHeight);
  const hasCustomCoordinates = anchor === "custom" && x !== null && y !== null;

  return {
    version: NOTIFICATION_LAYOUT_VERSION,
    anchor: hasCustomCoordinates ? "custom" : (anchor === "custom" ? DEFAULT_NOTIFICATION_LAYOUT.anchor : anchor),
    x: hasCustomCoordinates ? Math.max(0, Math.round(x)) : null,
    y: hasCustomCoordinates ? Math.max(0, Math.round(y)) : null,
    panelHeight: panelHeight === null
      ? null
      : Math.round(clamp(
        panelHeight,
        NOTIFICATION_PANEL_MIN_HEIGHT,
        NOTIFICATION_PANEL_MAX_HEIGHT,
      )),
    collapsed: typeof value.collapsed === "boolean"
      ? value.collapsed
      : DEFAULT_NOTIFICATION_LAYOUT.collapsed,
  };
}

export function loadNotificationLayout(storage) {
  try {
    const target = storage ?? globalThis.localStorage;
    const raw = target?.getItem?.(NOTIFICATION_LAYOUT_STORAGE_KEY);
    return raw ? normalizeNotificationLayout(JSON.parse(raw)) : { ...DEFAULT_NOTIFICATION_LAYOUT };
  } catch {
    return { ...DEFAULT_NOTIFICATION_LAYOUT };
  }
}

export function saveNotificationLayout(layout, storage) {
  const normalized = normalizeNotificationLayout(layout);
  try {
    const target = storage ?? globalThis.localStorage;
    target?.setItem?.(NOTIFICATION_LAYOUT_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Layout persistence is optional when browser storage is restricted.
  }
  return normalized;
}

export function clearNotificationLayout(storage) {
  try {
    const target = storage ?? globalThis.localStorage;
    target?.removeItem?.(NOTIFICATION_LAYOUT_STORAGE_KEY);
  } catch {
    // A blocked storage implementation should not block the reset action.
  }
}

export function clampFloatingPanelPosition(
  position,
  {
    panelWidth,
    panelHeight,
    viewportWidth,
    viewportHeight,
    margin = NOTIFICATION_PANEL_MARGIN,
  },
) {
  const safeMargin = Math.max(0, finiteNumber(margin) ?? NOTIFICATION_PANEL_MARGIN);
  const safePanelWidth = Math.max(0, finiteNumber(panelWidth) ?? 0);
  const safePanelHeight = Math.max(0, finiteNumber(panelHeight) ?? 0);
  const safeViewportWidth = Math.max(0, finiteNumber(viewportWidth) ?? 0);
  const safeViewportHeight = Math.max(0, finiteNumber(viewportHeight) ?? 0);
  const rawX = finiteNumber(position?.x) ?? safeMargin;
  const rawY = finiteNumber(position?.y) ?? safeMargin;

  return {
    x: Math.round(clamp(rawX, safeMargin, safeViewportWidth - safePanelWidth - safeMargin)),
    y: Math.round(clamp(rawY, safeMargin, safeViewportHeight - safePanelHeight - safeMargin)),
  };
}

export function anchorClassName(anchor) {
  return NOTIFICATION_PANEL_ANCHORS.includes(anchor)
    ? `is-${anchor}`
    : "is-custom";
}
