import { secureFetch } from "./lanAccess";

function timeoutError(timeoutMs) {
  const error = new Error(`API 請求逾時（${timeoutMs}ms）`);
  error.name = "TimeoutError";
  error.code = "QV_API_TIMEOUT";
  error.retryable = true;
  return error;
}

function createCombinedController(externalSignal, timeoutMs) {
  const controller = new AbortController();
  let timedOut = false;
  let timer = null;

  const forwardAbort = () => controller.abort(externalSignal?.reason);
  if (externalSignal) {
    if (externalSignal.aborted) forwardAbort();
    else externalSignal.addEventListener("abort", forwardAbort, { once: true });
  }
  if (timeoutMs > 0) {
    timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, timeoutMs);
  }

  return {
    signal: controller.signal,
    didTimeout: () => timedOut,
    dispose() {
      if (timer != null) clearTimeout(timer);
      externalSignal?.removeEventListener?.("abort", forwardAbort);
    },
  };
}

export async function fetchWithPolicy(url, options = {}, {
  timeoutMs = 15_000,
  retries = 0,
  retryDelayMs = 150,
} = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const maxRetries = method === "GET" ? Math.max(0, Number(retries) || 0) : 0;
  let attempt = 0;

  while (true) {
    const request = timeoutMs > 0 && typeof AbortController === "function"
      ? createCombinedController(options.signal, timeoutMs)
      : null;
    try {
      return await secureFetch(url, request ? { ...options, signal: request.signal } : options);
    } catch (error) {
      const normalizedError = request?.didTimeout() ? timeoutError(timeoutMs) : error;
      const retryable = normalizedError?.code === "QV_API_TIMEOUT" || normalizedError instanceof TypeError;
      if (attempt >= maxRetries || !retryable || options.signal?.aborted) throw normalizedError;
      await new Promise((resolve) => setTimeout(resolve, retryDelayMs));
      attempt += 1;
    } finally {
      request?.dispose();
    }
  }
}
