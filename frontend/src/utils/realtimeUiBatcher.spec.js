import { describe, expect, it, vi } from "vitest";

import { upsertRealtimeOhlcFromCandle, upsertRealtimeOhlcFromQuote } from "./realtimeOhlc";
import { createRealtimeUiBatcher } from "./realtimeUiBatcher";

function createFrameHarness() {
  const callbacks = new Map();
  let seed = 0;
  return {
    callbacks,
    requestFrame(callback) {
      seed += 1;
      callbacks.set(seed, callback);
      return seed;
    },
    cancelFrame(handle) {
      callbacks.delete(handle);
    },
    run() {
      const pending = [...callbacks.values()];
      callbacks.clear();
      pending.forEach((callback) => callback(16));
    },
  };
}

describe("realtimeUiBatcher", () => {
  it("coalesces 500 quotes into one paint with latest price and full extrema", () => {
    const frame = createFrameHarness();
    const updates = [];
    const batcher = createRealtimeUiBatcher({
      getActiveTicker: () => "2330.TW",
      onQuote: (message) => updates.push(message),
      requestFrame: frame.requestFrame,
      cancelFrame: frame.cancelFrame,
      documentRef: null,
    });

    for (let index = 0; index < 500; index += 1) {
      batcher.push({
        type: "quote",
        ticker: "2330.TW",
        data: {
          ticker: "2330.TW",
          price: 900 + index,
          high: index === 120 ? 1600 : 1400,
          low: index === 80 ? 800 : 850,
          volume: 1000 + index,
          quote_timestamp: `2026-07-23T01:${String(Math.floor(index / 60)).padStart(2, "0")}:${String(index % 60).padStart(2, "0")}Z`,
        },
      });
    }

    expect(frame.callbacks.size).toBe(1);
    frame.run();
    expect(updates).toHaveLength(1);
    expect(updates[0].data.price).toBe(1399);
    expect(updates[0].data.high).toBe(1600);
    expect(updates[0].data.low).toBe(800);
    expect(updates[0].data.volume).toBe(1499);
  });

  it("keeps total-volume delta correct after quote coalescing", () => {
    const frame = createFrameHarness();
    let rows = [{
      date: "2026-07-23 09:00:00",
      open: 100,
      high: 100,
      low: 100,
      close: 100,
      volume: 20,
    }];
    let displayedVolume = 100;
    const batcher = createRealtimeUiBatcher({
      getActiveTicker: () => "TXF",
      onQuote: ({ data }) => {
        rows = upsertRealtimeOhlcFromQuote(rows, {
          ...data,
          previous_total_volume: displayedVolume,
        }, "1m");
        displayedVolume = data.volume;
      },
      requestFrame: frame.requestFrame,
      cancelFrame: frame.cancelFrame,
      documentRef: null,
    });

    batcher.push({
      type: "quote",
      ticker: "TXF",
      data: { ticker: "TXF", price: 101, volume: 120, quote_timestamp: "2026-07-23T09:00:20+08:00" },
    });
    batcher.push({
      type: "quote",
      ticker: "TXF",
      data: { ticker: "TXF", price: 102, volume: 150, quote_timestamp: "2026-07-23T09:00:40+08:00" },
    });
    frame.run();

    expect(rows.at(-1).close).toBe(102);
    expect(rows.at(-1).volume).toBe(70);
  });

  it("applies candles immediately and creates consecutive minute buckets", () => {
    let rows = [{
      date: "2026-07-23 09:00:00",
      open: 100,
      high: 100,
      low: 100,
      close: 100,
      volume: 1,
    }];
    const batcher = createRealtimeUiBatcher({
      getActiveTicker: () => "TXF",
      onCandle: ({ data }) => {
        rows = upsertRealtimeOhlcFromCandle(rows, data, "1m");
      },
      documentRef: null,
    });

    batcher.push({
      type: "candle",
      ticker: "TXF",
      data: { date: "2026-07-23T09:01:00+08:00", open: 101, high: 102, low: 100, close: 102, volume: 5 },
    });
    batcher.push({
      type: "candle",
      ticker: "TXF",
      data: { date: "2026-07-23T09:02:00+08:00", open: 102, high: 104, low: 102, close: 103, volume: 6 },
    });

    expect(rows.map((row) => row.date)).toEqual([
      "2026-07-23 09:00:00",
      "2026-07-23 09:01:00",
      "2026-07-23 09:02:00",
    ]);
  });

  it("keeps only the latest books snapshot and isolates ticker switches", () => {
    const frame = createFrameHarness();
    const books = [];
    const quotes = [];
    let activeTicker = "AAPL";
    const batcher = createRealtimeUiBatcher({
      getActiveTicker: () => activeTicker,
      onQuote: (message) => quotes.push(message),
      onBooks: (message) => books.push(message),
      requestFrame: frame.requestFrame,
      cancelFrame: frame.cancelFrame,
      documentRef: null,
    });

    batcher.push({ type: "quote", ticker: "AAPL", data: { ticker: "AAPL", price: 1 }, ts: 1 });
    batcher.push({ type: "books", ticker: "AAPL", data: { bids: [{ price: 1 }] }, ts: 1 });
    batcher.push({ type: "books", ticker: "AAPL", data: { bids: [{ price: 2 }] }, ts: 2 });
    batcher.clearTicker("AAPL");
    activeTicker = "MSFT";
    batcher.push({ type: "quote", ticker: "MSFT", data: { ticker: "MSFT", price: 3 }, ts: 3 });
    batcher.push({ type: "books", ticker: "MSFT", data: { bids: [{ price: 4 }] }, ts: 4 });
    frame.run();

    expect(quotes.map((message) => message.ticker)).toEqual(["MSFT"]);
    expect(books).toHaveLength(1);
    expect(books[0].data.bids[0].price).toBe(4);
  });

  it("flushes immediately when visible and cleans timers and listeners on destroy", () => {
    let visibilityListener;
    const documentRef = {
      hidden: true,
      addEventListener: vi.fn((_event, listener) => {
        visibilityListener = listener;
      }),
      removeEventListener: vi.fn(),
    };
    const clearTimer = vi.fn();
    const updates = [];
    const batcher = createRealtimeUiBatcher({
      getActiveTicker: () => "AAPL",
      onQuote: (message) => updates.push(message),
      documentRef,
      setTimer: () => 9,
      clearTimer,
    });

    batcher.push({ type: "quote", ticker: "AAPL", data: { ticker: "AAPL", price: 1 } });
    expect(updates).toEqual([]);
    documentRef.hidden = false;
    visibilityListener();
    expect(updates).toHaveLength(1);
    expect(clearTimer).toHaveBeenCalledWith(9);

    batcher.push({ type: "quote", ticker: "AAPL", data: { ticker: "AAPL", price: 2 } });
    batcher.destroy();
    expect(batcher.pendingCount()).toBe(0);
    expect(documentRef.removeEventListener).toHaveBeenCalledWith("visibilitychange", visibilityListener);
  });
});
