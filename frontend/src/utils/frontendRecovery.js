const FRONTEND_ERROR_EVENT = "quantvision:frontend-error";

export function categorizeFrontendError(error) {
  const name = String(error?.name || "").toLowerCase();
  const message = String(error?.message || error || "").toLowerCase();

  if (name === "aborterror") return "request_aborted";
  if (name === "timeouterror" || message.includes("timeout") || message.includes("逾時")) {
    return "request_timeout";
  }
  if (
    message.includes("dynamically imported module")
    || message.includes("failed to fetch dynamically imported module")
    || message.includes("loading chunk")
    || message.includes("chunkloaderror")
  ) {
    return "module_load";
  }
  if (error instanceof TypeError && message.includes("fetch")) return "network";
  if (message.includes("render") || message.includes("component")) return "render";
  return "unexpected";
}

export function reportFrontendError(error, source = "runtime") {
  const detail = {
    category: categorizeFrontendError(error),
    source: String(source || "runtime"),
  };
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(FRONTEND_ERROR_EVENT, { detail }));
  }
  return detail;
}

export function installUnhandledRejectionReporter(target = globalThis.window) {
  if (!target?.addEventListener) return () => {};
  const handler = (event) => {
    const category = categorizeFrontendError(event?.reason);
    // Superseded ticker/route requests are intentionally aborted and are not UI failures.
    if (category === "request_aborted") return;
    const detail = reportFrontendError(event?.reason, "unhandledrejection");
    // Do not log the original exception or rejected payload: it can contain API data.
    console.error("[QuantVision frontend]", detail);
  };
  target.addEventListener("unhandledrejection", handler);
  return () => target.removeEventListener("unhandledrejection", handler);
}

export function frontendErrorEventName() {
  return FRONTEND_ERROR_EVENT;
}
