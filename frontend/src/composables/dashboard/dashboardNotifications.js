const ICON_BY_CATEGORY = {
  alert: "⚡",
  system: "ℹ",
};

const ICON_BY_LEVEL = {
  warning: "⚠️",
  error: "⛔",
  success: "✅",
  info: "ℹ",
};

export function extractContextGroupName(payload = {}) {
  if (payload?.context_group_name) return String(payload.context_group_name);
  const groupTag = (Array.isArray(payload?.context_tags) ? payload.context_tags : []).find((tag) =>
    String(tag || "").startsWith("觀察群組:"),
  );
  return groupTag ? String(groupTag).slice("觀察群組:".length) : "";
}

export function mapDashboardNotification(item, formatTimestamp) {
  const quote = item.payload?.quote || {};
  const rawTicker = quote.ticker || item.payload?.ticker || null;
  const isMacroNotification =
    String(rawTicker || "").toUpperCase() === "MARKET" || Boolean(quote.macro_summary);
  const contextTags = Array.isArray(item.payload?.context_tags)
    ? item.payload.context_tags.filter(Boolean).slice(0, 4)
    : [];

  return {
    id: `remote-${item.id}`,
    remoteId: item.id,
    icon: ICON_BY_CATEGORY[item.category] || ICON_BY_LEVEL[item.level] || "ℹ",
    title: item.title,
    msg: item.message,
    type: item.level || "",
    level: item.level || "info",
    category: item.category || "system",
    read: Boolean(item.read_at),
    persisted: true,
    source: quote.source || item.payload?.source || "local_db",
    ticker: isMacroNotification ? null : rawTicker,
    workspaceTarget: isMacroNotification ? "macro" : null,
    contextSource: item.payload?.context_source || "",
    contextGroupName: extractContextGroupName(item.payload),
    contextTags,
    macroSummary: item.payload?.macro_summary || null,
    triggerValue: item.payload?.trigger_value ?? null,
    thresholdValue: item.payload?.threshold_value ?? null,
    payload: item.payload || {},
    relatedEntityType: item.related_entity_type || null,
    relatedEntityId: item.related_entity_id || null,
    createdAt: item.created_at || null,
    time: formatTimestamp(item.created_at),
  };
}

export function createDashboardNotifications({
  dashboardApi,
  localNotifications,
  remoteNotifications,
  formatTimestamp,
  schedule = (callback, delay) => globalThis.setTimeout(callback, delay),
  now = () => new Date(),
  random = () => Math.random(),
  reportError = (error) => console.error(error),
}) {
  const mapRemoteNotification = (item) => mapDashboardNotification(item, formatTimestamp);

  function pushNotification({ icon, title, msg, type = "" }) {
    const createdAt = now().toISOString();
    const id = `${Date.parse(createdAt)}-${random()}`;
    localNotifications.value = [
      ...localNotifications.value,
      {
        id,
        icon,
        title,
        msg,
        type,
        level: type || "info",
        category: "session",
        read: false,
        persisted: false,
        ticker: null,
        source: "session",
        createdAt,
        time: new Date(createdAt).toLocaleTimeString("zh-TW"),
      },
    ];
    schedule(() => dismissNotification(id), 6000);
  }

  async function dismissNotification(id) {
    const remoteTarget = remoteNotifications.value.find((item) => item.id === id);
    if (remoteTarget?.remoteId != null) {
      try {
        const record = await dashboardApi.markNotificationRead(remoteTarget.remoteId);
        remoteNotifications.value = remoteNotifications.value.map((item) =>
          item.id === id ? mapRemoteNotification(record) : item,
        );
      } catch (error) {
        reportError(error);
      }
      return;
    }
    localNotifications.value = localNotifications.value.filter((item) => item.id !== id);
  }

  async function loadNotifications({ silent = true } = {}) {
    try {
      const response = await dashboardApi.listNotifications({ unreadOnly: false, limit: 50 });
      remoteNotifications.value = Array.isArray(response?.items)
        ? response.items.map((item) => mapRemoteNotification(item))
        : [];
    } catch (error) {
      reportError(error);
      if (!silent) {
        pushNotification({ icon: "⚠️", title: "通知載入失敗", msg: "請稍後再試", type: "error" });
      }
    }
  }

  async function setNotificationRead(notificationId, read) {
    if (!notificationId) return;
    const target = remoteNotifications.value.find((item) => item.id === notificationId);
    if (!target?.remoteId) return;
    try {
      const record = await dashboardApi.setNotificationReadState(target.remoteId, read);
      remoteNotifications.value = remoteNotifications.value.map((item) =>
        item.id === notificationId ? mapRemoteNotification(record) : item,
      );
    } catch (error) {
      reportError(error);
      pushNotification({
        icon: "!",
        title: read ? "Mark read failed" : "Mark unread failed",
        msg: error.message || "Please try again later",
        type: "error",
      });
    }
  }

  return {
    dismissNotification,
    loadNotifications,
    mapRemoteNotification,
    pushNotification,
    setNotificationRead,
  };
}
