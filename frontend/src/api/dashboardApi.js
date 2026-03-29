function normalizeBaseUrl(baseUrl = "") {
  return String(baseUrl || "").replace(/\/$/, "");
}

function buildJsonRequest(method, body) {
  return {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

export function createDashboardApi({ baseUrl = "" } = {}) {
  const normalizedBaseUrl = normalizeBaseUrl(baseUrl);

  async function request(path, options = {}) {
    const response = await fetch(`${normalizedBaseUrl}${path}`, options);
    const contentType = response.headers?.get?.("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : null;
    if (!response.ok) {
      const error = new Error(payload?.detail || `HTTP ${response.status}`);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  return {
    listWorkspaces() {
      return request("/api/workspaces");
    },
    getWorkspace(workspaceId) {
      return request(`/api/workspaces/${workspaceId}`);
    },
    createWorkspace(payload) {
      return request("/api/workspaces", buildJsonRequest("POST", payload));
    },
    updateWorkspace(workspaceId, payload) {
      return request(`/api/workspaces/${workspaceId}`, buildJsonRequest("PUT", payload));
    },
    deleteWorkspace(workspaceId) {
      return request(`/api/workspaces/${workspaceId}`, { method: "DELETE" });
    },
    listAlerts() {
      return request("/api/alerts");
    },
    createAlert(payload) {
      return request("/api/alerts", buildJsonRequest("POST", payload));
    },
    updateAlert(alertId, payload) {
      return request(`/api/alerts/${alertId}`, buildJsonRequest("PATCH", payload));
    },
    deleteAlert(alertId) {
      return request(`/api/alerts/${alertId}`, { method: "DELETE" });
    },
    listNotifications(options = {}) {
      const params = new URLSearchParams();
      if (options.unreadOnly) params.set("unread_only", "true");
      if (options.limit != null) params.set("limit", String(options.limit));
      const query = params.toString();
      return request(`/api/notifications${query ? `?${query}` : ""}`);
    },
    markNotificationRead(notificationId) {
      return request(`/api/notifications/${notificationId}/read`, { method: "POST" });
    },
    getQuote(ticker) {
      return request(`/api/quote/${encodeURIComponent(ticker)}`);
    },
  };
}

export const dashboardApi = createDashboardApi();
