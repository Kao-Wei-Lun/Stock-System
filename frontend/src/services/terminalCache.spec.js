import { describe, expect, it } from "vitest";

import {
  TERMINAL_CACHE_DB_NAME,
  TERMINAL_CACHE_SCHEMA_VERSION,
  createTerminalCache,
  resetIndexedDbTerminalCache,
} from "./terminalCache";

function createMemoryDriver() {
  const stores = { snapshots: new Map(), metadata: new Map() };
  return {
    stores,
    async get(store, key) { return stores[store].get(key) || null; },
    async put(store, value) { stores[store].set(value.key, structuredClone(value)); },
    async delete(store, key) { stores[store].delete(key); },
    async getAll(store) { return [...stores[store].values()]; },
    async clear() { Object.values(stores).forEach((store) => store.clear()); },
  };
}

const rows = (count = 3) => Array.from({ length: count }, (_, index) => ({
  date: `2026-07-23T09:${String(index).padStart(2, "0")}:00+08:00`,
  close: 100 + index,
}));

describe("terminalCache", () => {
  it("stores bounded OHLC snapshots by ticker and interval", async () => {
    const driver = createMemoryDriver();
    const cache = createTerminalCache({ driver, now: () => 1000 });

    expect(await cache.writeOhlc({ ticker: "*tmff", interval: "1M", rows: rows() })).toBe(true);
    const record = await cache.readOhlc({ ticker: "*TMFF", interval: "1m" });

    expect(record.schemaVersion).toBe(TERMINAL_CACHE_SCHEMA_VERSION);
    expect(record.latestCandleTime).toContain("09:02");
    expect(record.rows).toHaveLength(3);
  });

  it("ignores and deletes corrupt, reversed, expired, or wrong-version records", async () => {
    const driver = createMemoryDriver();
    const key = "*TMFF::1m";
    const cache = createTerminalCache({ driver, now: () => 10_000, maxAgeMs: 1000 });
    for (const record of [
      { key, schemaVersion: 0, savedAt: 10_000, rows: rows() },
      { key, schemaVersion: 1, savedAt: 10_000, rows: [...rows()].reverse() },
      { key, schemaVersion: 1, savedAt: 1, rows: rows() },
    ]) {
      driver.stores.snapshots.set(key, record);
      expect(await cache.readOhlc({ ticker: "*TMFF", interval: "1m" })).toBeNull();
      expect(driver.stores.snapshots.has(key)).toBe(false);
    }
  });

  it("evicts oldest entries and clears all non-authoritative local data", async () => {
    let time = 0;
    const driver = createMemoryDriver();
    const cache = createTerminalCache({ driver, now: () => ++time, maxEntries: 2 });
    await cache.writeOhlc({ ticker: "A", interval: "1d", rows: rows() });
    await cache.writeOhlc({ ticker: "B", interval: "1d", rows: rows() });
    await cache.writeOhlc({ ticker: "C", interval: "1d", rows: rows() });
    await cache.writeWatchlistMetadata({ groups: [] });

    expect(driver.stores.snapshots.size).toBe(2);
    expect(driver.stores.snapshots.has("A::1d")).toBe(false);
    await cache.clear();
    expect(driver.stores.snapshots.size).toBe(0);
    expect(driver.stores.metadata.size).toBe(0);
  });

  it("deletes only the QuantVision terminal cache database during recovery", async () => {
    let deletedName = null;
    const indexedDb = {
      deleteDatabase(name) {
        deletedName = name;
        const request = {};
        queueMicrotask(() => request.onsuccess());
        return request;
      },
    };

    await expect(resetIndexedDbTerminalCache(indexedDb)).resolves.toBe(true);
    expect(deletedName).toBe(TERMINAL_CACHE_DB_NAME);
  });
});
