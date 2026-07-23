export const TERMINAL_CACHE_DB_NAME = "quantvision-terminal-cache";
const DB_VERSION = 1;
const SNAPSHOT_STORE = "snapshots";
const METADATA_STORE = "metadata";

export const TERMINAL_CACHE_SCHEMA_VERSION = 1;
export const TERMINAL_CACHE_MAX_ROWS = 500;

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("IndexedDB request failed"));
  });
}

function isRecoverableIndexedDbError(error) {
  return new Set([
    "AbortError",
    "InvalidStateError",
    "NotFoundError",
    "UnknownError",
    "VersionError",
  ]).has(String(error?.name || ""));
}

export function resetIndexedDbTerminalCache(indexedDb = globalThis.indexedDB) {
  if (!indexedDb?.deleteDatabase) return Promise.resolve(false);
  return new Promise((resolve) => {
    const request = indexedDb.deleteDatabase(TERMINAL_CACHE_DB_NAME);
    request.onsuccess = () => resolve(true);
    request.onerror = () => resolve(false);
    request.onblocked = () => resolve(false);
  });
}

export function createIndexedDbTerminalCacheDriver(indexedDb = globalThis.indexedDB) {
  let openPromise = null;
  let databaseHandle = null;

  function openOnce() {
    return new Promise((resolve, reject) => {
        const request = indexedDb.open(TERMINAL_CACHE_DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
          const database = request.result;
          if (!database.objectStoreNames.contains(SNAPSHOT_STORE)) {
            database.createObjectStore(SNAPSHOT_STORE, { keyPath: "key" });
          }
          if (!database.objectStoreNames.contains(METADATA_STORE)) {
            database.createObjectStore(METADATA_STORE, { keyPath: "key" });
          }
        };
        request.onsuccess = () => {
          databaseHandle = request.result;
          databaseHandle.onversionchange = () => {
            databaseHandle?.close();
            databaseHandle = null;
            openPromise = null;
          };
          resolve(databaseHandle);
        };
        request.onerror = () => reject(request.error || new Error("Unable to open terminal cache"));
      });
  }

  async function recover() {
    databaseHandle?.close();
    databaseHandle = null;
    openPromise = null;
    await resetIndexedDbTerminalCache(indexedDb);
    return openOnce();
  }

  function open() {
    if (!indexedDb) return Promise.resolve(null);
    if (!openPromise) {
      openPromise = openOnce()
        .catch(async (error) => {
          if (!isRecoverableIndexedDbError(error)) return null;
          try {
            return await recover();
          } catch {
            return null;
          }
        });
    }
    return openPromise;
  }

  async function run(storeName, mode, operation) {
    async function execute(database) {
      const transaction = database.transaction(storeName, mode);
      return operation(transaction.objectStore(storeName));
    }

    const database = await open();
    if (!database) return null;
    try {
      return await execute(database);
    } catch (error) {
      if (!isRecoverableIndexedDbError(error)) throw error;
      const recovered = await recover().catch(() => null);
      return recovered ? execute(recovered) : null;
    }
  }

  return {
    get: (store, key) => run(store, "readonly", (objectStore) => requestResult(objectStore.get(key))),
    put: (store, value) => run(store, "readwrite", (objectStore) => requestResult(objectStore.put(value))),
    delete: (store, key) => run(store, "readwrite", (objectStore) => requestResult(objectStore.delete(key))),
    getAll: (store) => run(store, "readonly", (objectStore) => requestResult(objectStore.getAll())),
    clear: async () => {
      await Promise.all([
        run(SNAPSHOT_STORE, "readwrite", (objectStore) => requestResult(objectStore.clear())),
        run(METADATA_STORE, "readwrite", (objectStore) => requestResult(objectStore.clear())),
      ]);
    },
    reset: async () => {
      databaseHandle?.close();
      databaseHandle = null;
      openPromise = null;
      return resetIndexedDbTerminalCache(indexedDb);
    },
  };
}

function normalizedKey(ticker, interval) {
  return `${String(ticker || "").trim().toUpperCase()}::${String(interval || "").trim().toLowerCase()}`;
}

function validOrderedRows(rows) {
  if (!Array.isArray(rows) || !rows.length || rows.length > TERMINAL_CACHE_MAX_ROWS) return false;
  let previous = -Infinity;
  for (const row of rows) {
    const timestamp = Date.parse(String(row?.date || "").replace(" ", "T"));
    if (!Number.isFinite(timestamp) || timestamp <= previous) return false;
    previous = timestamp;
  }
  return true;
}

export function createTerminalCache({
  driver = createIndexedDbTerminalCacheDriver(),
  now = () => Date.now(),
  maxEntries = 8,
  maxAgeMs = 7 * 24 * 60 * 60 * 1000,
} = {}) {
  async function safe(operation, fallback = null) {
    try {
      return await operation();
    } catch {
      return fallback;
    }
  }

  async function readOhlc({ ticker, interval }) {
    const key = normalizedKey(ticker, interval);
    return safe(async () => {
      const record = await driver.get(SNAPSHOT_STORE, key);
      const invalid = !record
        || record.schemaVersion !== TERMINAL_CACHE_SCHEMA_VERSION
        || record.key !== key
        || now() - Number(record.savedAt || 0) > maxAgeMs
        || !validOrderedRows(record.rows);
      if (invalid) {
        if (record) await driver.delete(SNAPSHOT_STORE, key);
        return null;
      }
      return record;
    });
  }

  async function writeOhlc({ ticker, interval, rows }) {
    const boundedRows = Array.isArray(rows) ? rows.slice(-TERMINAL_CACHE_MAX_ROWS) : [];
    if (!validOrderedRows(boundedRows)) return false;
    const key = normalizedKey(ticker, interval);
    return safe(async () => {
      await driver.put(SNAPSHOT_STORE, {
        key,
        schemaVersion: TERMINAL_CACHE_SCHEMA_VERSION,
        ticker: String(ticker || "").trim().toUpperCase(),
        interval: String(interval || "").trim().toLowerCase(),
        savedAt: now(),
        latestCandleTime: boundedRows.at(-1)?.date || null,
        rows: boundedRows,
      });
      const records = (await driver.getAll(SNAPSHOT_STORE)) || [];
      const overflow = records
        .sort((left, right) => Number(right.savedAt || 0) - Number(left.savedAt || 0))
        .slice(Math.max(1, maxEntries));
      await Promise.all(overflow.map((record) => driver.delete(SNAPSHOT_STORE, record.key)));
      return true;
    }, false);
  }

  async function readWatchlistMetadata() {
    return safe(async () => {
      const record = await driver.get(METADATA_STORE, "watchlist");
      if (!record || record.schemaVersion !== TERMINAL_CACHE_SCHEMA_VERSION || !Array.isArray(record.payload?.groups)) {
        if (record) await driver.delete(METADATA_STORE, "watchlist");
        return null;
      }
      return record;
    });
  }

  async function writeWatchlistMetadata(payload) {
    if (!Array.isArray(payload?.groups)) return false;
    return safe(async () => {
      await driver.put(METADATA_STORE, {
        key: "watchlist",
        schemaVersion: TERMINAL_CACHE_SCHEMA_VERSION,
        savedAt: now(),
        payload,
      });
      return true;
    }, false);
  }

  return {
    readOhlc,
    writeOhlc,
    readWatchlistMetadata,
    writeWatchlistMetadata,
    clear: () => safe(() => driver.clear()),
  };
}
