import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createDashboardRealtime,
  resetDashboardRealtimeForTests,
} from "./dashboardRealtime";

class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances = [];

  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.sent = [];
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    MockWebSocket.instances.push(this);
  }

  send(payload) {
    this.sent.push(payload);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  open() {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.();
  }

  receive(message) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }

  serverClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }
}

describe("dashboardRealtime", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    resetDashboardRealtimeForTests();
  });

  afterEach(() => {
    resetDashboardRealtimeForTests();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("shares a single websocket across dashboard consumers", () => {
    const firstMessages = [];
    const secondMessages = [];
    const first = createDashboardRealtime({
      wsUrl: "ws://localhost:8001/ws",
      onMessage: (message) => firstMessages.push(message),
    });
    const second = createDashboardRealtime({
      wsUrl: "ws://localhost:8001/ws",
      onMessage: (message) => secondMessages.push(message),
    });

    first.connect();
    second.connect();
    first.subscribeTicker("AAPL");

    expect(MockWebSocket.instances).toHaveLength(1);

    const socket = MockWebSocket.instances[0];
    socket.open();
    socket.receive({ type: "quote", data: { ticker: "AAPL", price: 123 } });

    expect(first.wsConnected.value).toBe(true);
    expect(second.wsConnected.value).toBe(true);
    expect(socket.sent).toEqual([
      JSON.stringify({ action: "subscribe", ticker: "AAPL" }),
    ]);
    expect(firstMessages).toEqual([{ type: "quote", data: { ticker: "AAPL", price: 123 } }]);
    expect(secondMessages).toEqual([{ type: "quote", data: { ticker: "AAPL", price: 123 } }]);

    second.disconnect();
    expect(socket.readyState).toBe(MockWebSocket.OPEN);

    first.disconnect();
    expect(socket.readyState).toBe(MockWebSocket.CLOSED);
  });

  it("does not reconnect after the last consumer disconnects intentionally", () => {
    const realtime = createDashboardRealtime({ wsUrl: "ws://localhost:8001/ws" });

    realtime.connect();
    expect(MockWebSocket.instances).toHaveLength(1);

    const socket = MockWebSocket.instances[0];
    socket.open();
    realtime.disconnect();

    vi.advanceTimersByTime(5000);

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(socket.readyState).toBe(MockWebSocket.CLOSED);
    expect(realtime.wsConnected.value).toBe(false);
  });

  it("reconnects after an unexpected close while a consumer is still active", () => {
    const realtime = createDashboardRealtime({ wsUrl: "ws://localhost:8001/ws" });

    realtime.connect();
    realtime.subscribeTicker("MSFT");

    const socket = MockWebSocket.instances[0];
    socket.open();
    socket.serverClose();

    expect(realtime.wsConnected.value).toBe(false);

    vi.advanceTimersByTime(5000);

    expect(MockWebSocket.instances).toHaveLength(2);
    const reconnectedSocket = MockWebSocket.instances[1];
    reconnectedSocket.open();

    expect(reconnectedSocket.sent).toEqual([
      JSON.stringify({ action: "subscribe", ticker: "MSFT" }),
    ]);

    realtime.disconnect();
  });
});
