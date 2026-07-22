function pageIsVisible() {
  return typeof document === "undefined" || document.visibilityState !== "hidden";
}

export function createVisibilityPoller(task, {
  intervalMs,
  runImmediately = false,
  pauseWhenHidden = true,
} = {}) {
  const delay = Math.max(100, Number(intervalMs) || 1000);
  let active = false;
  let timerId = null;
  let inFlight = null;
  let listening = false;

  function clearTimer() {
    if (timerId == null) return;
    window.clearTimeout(timerId);
    timerId = null;
  }

  function schedule() {
    clearTimer();
    if (!active || (pauseWhenHidden && !pageIsVisible())) return;
    timerId = window.setTimeout(() => {
      timerId = null;
      void run().catch(() => {});
    }, delay);
  }

  function run({ force = false } = {}) {
    if (inFlight) return inFlight;
    if (!force && pauseWhenHidden && !pageIsVisible()) return Promise.resolve(undefined);
    clearTimer();
    inFlight = Promise.resolve()
      .then(task)
      .finally(() => {
        inFlight = null;
        schedule();
      });
    return inFlight;
  }

  function handleVisibilityChange() {
    if (!pageIsVisible()) {
      clearTimer();
      return;
    }
    if (active) void run().catch(() => {});
  }

  function start({ immediate = runImmediately } = {}) {
    if (active) return;
    active = true;
    if (pauseWhenHidden && typeof document !== "undefined" && !listening) {
      document.addEventListener("visibilitychange", handleVisibilityChange);
      listening = true;
    }
    if (immediate && pageIsVisible()) void run().catch(() => {});
    else schedule();
  }

  function stop() {
    active = false;
    clearTimer();
    if (listening && typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      listening = false;
    }
  }

  return {
    start,
    stop,
    runNow: () => run({ force: true }),
    isRunning: () => active,
    isRequestInFlight: () => inFlight !== null,
  };
}
