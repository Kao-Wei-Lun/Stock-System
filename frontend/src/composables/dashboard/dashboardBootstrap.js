import { reactive } from "vue";


function createResourceState() {
  return {
    status: "idle",
    queryKey: null,
    error: null,
    loadedAt: null,
    value: undefined,
  };
}

export function createDashboardBootstrap({ scheduleIdle } = {}) {
  const resources = reactive({});
  const flights = new Map();
  const deferredHandles = new Set();
  const deferredKeys = new Set();
  const enqueueIdle = scheduleIdle || ((callback) => {
    if (typeof globalThis.requestIdleCallback === "function") {
      return { type: "idle", id: globalThis.requestIdleCallback(callback, { timeout: 1500 }) };
    }
    return { type: "timeout", id: globalThis.setTimeout(callback, 0) };
  });

  function getResourceState(name) {
    if (!resources[name]) resources[name] = createResourceState();
    return resources[name];
  }

  function ensure(name, loader, { queryKey = "default", force = false } = {}) {
    const resource = getResourceState(name);
    const normalizedQueryKey = String(queryKey);
    const flightKey = `${name}:${normalizedQueryKey}`;
    if (flights.has(flightKey)) return flights.get(flightKey);
    if (!force && resource.status === "ready" && resource.queryKey === normalizedQueryKey) {
      return Promise.resolve(resource.value);
    }

    resource.status = "loading";
    resource.queryKey = normalizedQueryKey;
    resource.error = null;
    const promise = Promise.resolve()
      .then(loader)
      .then((value) => {
        if (resource.queryKey === normalizedQueryKey) {
          resource.status = "ready";
          resource.error = null;
          resource.loadedAt = new Date().toISOString();
          resource.value = value;
        }
        return value;
      })
      .catch((error) => {
        if (resource.queryKey === normalizedQueryKey) {
          resource.status = "error";
          resource.error = error?.message || String(error);
        }
        throw error;
      })
      .finally(() => {
        if (flights.get(flightKey) === promise) flights.delete(flightKey);
      });
    flights.set(flightKey, promise);
    return promise;
  }

  function defer(name, loader, options = {}) {
    const deferredKey = `${name}:${String(options.queryKey || "default")}`;
    if (deferredKeys.has(deferredKey) || flights.has(deferredKey)) return null;
    deferredKeys.add(deferredKey);
    const handle = enqueueIdle(() => {
      deferredHandles.delete(handle);
      deferredKeys.delete(deferredKey);
      void ensure(name, loader, options).catch(() => {});
    });
    deferredHandles.add(handle);
    return handle;
  }

  function cancelDeferred() {
    for (const handle of deferredHandles) {
      if (handle?.type === "idle" && typeof globalThis.cancelIdleCallback === "function") {
        globalThis.cancelIdleCallback(handle.id);
      } else {
        globalThis.clearTimeout(handle?.id);
      }
    }
    deferredHandles.clear();
    deferredKeys.clear();
  }

  return {
    resources,
    ensure,
    defer,
    cancelDeferred,
    getResourceState,
    isInFlight: (name, queryKey = "default") => flights.has(`${name}:${String(queryKey)}`),
  };
}
