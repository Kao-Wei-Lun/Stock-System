import { afterEach, describe, expect, it, vi } from "vitest";

import {
  categorizeFrontendError,
  installUnhandledRejectionReporter,
} from "./frontendRecovery";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("frontendRecovery", () => {
  it("classifies rejected dynamic imports without exposing their payload", () => {
    const error = new TypeError("Failed to fetch dynamically imported module: /app/secret-token.js");

    expect(categorizeFrontendError(error)).toBe("module_load");
  });

  it("logs only a sanitized category for unhandled rejections", () => {
    const target = new EventTarget();
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    const uninstall = installUnhandledRejectionReporter(target);
    const event = new Event("unhandledrejection");
    Object.defineProperty(event, "reason", {
      value: new Error("customer-private-payload"),
    });

    target.dispatchEvent(event);

    expect(errorLog).toHaveBeenCalledWith(
      "[QuantVision frontend]",
      { category: "unexpected", source: "unhandledrejection" },
    );
    expect(JSON.stringify(errorLog.mock.calls)).not.toContain("customer-private-payload");
    uninstall();
  });

  it("ignores expected request aborts during fast route changes", () => {
    const target = new EventTarget();
    const errorLog = vi.spyOn(console, "error").mockImplementation(() => {});
    const uninstall = installUnhandledRejectionReporter(target);
    const event = new Event("unhandledrejection");
    Object.defineProperty(event, "reason", {
      value: new DOMException("superseded", "AbortError"),
    });

    target.dispatchEvent(event);

    expect(errorLog).not.toHaveBeenCalled();
    uninstall();
  });
});
