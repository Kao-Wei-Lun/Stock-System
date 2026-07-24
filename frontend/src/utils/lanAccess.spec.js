import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearLanAccessToken,
  isLanBrowserLocation,
  readLanAccessToken,
  secureFetch,
  setLanAccessToken,
  websocketLanProtocols,
  withLanSecurityHeaders,
} from "./lanAccess";

afterEach(() => {
  clearLanAccessToken();
  vi.unstubAllGlobals();
});

describe("LAN access security", () => {
  it("distinguishes loopback from private network browser locations", () => {
    expect(isLanBrowserLocation({ hostname: "127.0.0.1" })).toBe(false);
    expect(isLanBrowserLocation({ hostname: "localhost" })).toBe(false);
    expect(isLanBrowserLocation({ hostname: "192.168.50.10" })).toBe(true);
  });

  it("keeps the token in session storage and sends it only in headers", () => {
    setLanAccessToken("secret-value");
    const options = withLanSecurityHeaders({ method: "POST", headers: { "Content-Type": "application/json" } });

    expect(readLanAccessToken()).toBe("secret-value");
    expect(options.headers.get("Authorization")).toBe("Bearer secret-value");
    expect(options.headers.get("X-Requested-With")).toBe("QuantVision");
  });

  it("wraps fetch without adding the token to the request URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    setLanAccessToken("secret-value");

    await secureFetch("/api/assets/accounts");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/assets/accounts");
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer secret-value");
  });

  it("re-prompts once and retries after a rejected LAN token", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 401 })
      .mockResolvedValueOnce({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    vi.stubGlobal("location", { hostname: "192.168.50.10" });
    vi.stubGlobal("prompt", vi.fn().mockReturnValue("fresh-secret"));
    setLanAccessToken("stale-secret");

    const response = await secureFetch("/api/assets/accounts");

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock.mock.calls[0][1].headers.get("Authorization")).toBe("Bearer stale-secret");
    expect(fetchMock.mock.calls[1][1].headers.get("Authorization")).toBe("Bearer fresh-secret");
    expect(readLanAccessToken()).toBe("fresh-secret");
  });

  it("encodes WebSocket authentication as a subprotocol instead of a URL query", () => {
    setLanAccessToken("含中文-token");
    const protocols = websocketLanProtocols();

    expect(protocols[0]).toBe("qv-access");
    expect(protocols[1]).toMatch(/^qv-token\.[A-Za-z0-9_-]+$/);
    expect(protocols.join(",")).not.toContain("含中文");
  });
});
