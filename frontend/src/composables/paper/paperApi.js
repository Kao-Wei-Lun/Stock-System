import { fetchWithPolicy } from "../../utils/requestPolicy";

export function createPaperApi({ baseUrl = "/api/paper-trading" } = {}) {
  const activeRequestControllers = new Set();

  async function apiFetch(path, options = {}) {
    const controller = new AbortController();
    activeRequestControllers.add(controller);
    try {
      const requestOptions = {
        headers: { "Content-Type": "application/json" },
        ...options,
        signal: controller.signal,
      };
      const response = await fetchWithPolicy(`${baseUrl}${path}`, requestOptions, {
        timeoutMs: 12_000,
        retries: String(options.method || "GET").toUpperCase() === "GET" ? 1 : 0,
      });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail || `API error: ${response.status}`);
      }
      return response.json();
    } finally {
      activeRequestControllers.delete(controller);
    }
  }

  function dispose() {
    activeRequestControllers.forEach((controller) => controller.abort());
    activeRequestControllers.clear();
  }

  return {
    apiFetch,
    dispose,
    pendingCount: () => activeRequestControllers.size,
  };
}
