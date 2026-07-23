export function createDashboardRouteControllers(definitions = {}) {
  let activeName = null;
  let activationToken = 0;
  let disposed = false;

  async function activate(name) {
    if (disposed) return false;
    const normalized = Object.prototype.hasOwnProperty.call(definitions, name) ? name : "overview";
    if (activeName === normalized) return true;
    const token = ++activationToken;
    if (activeName) await definitions[activeName]?.deactivate?.();
    if (token !== activationToken || disposed) return false;
    activeName = normalized;
    await definitions[normalized]?.activate?.({ token });
    return token === activationToken && !disposed;
  }

  async function dispose() {
    disposed = true;
    activationToken += 1;
    if (activeName) await definitions[activeName]?.deactivate?.();
    activeName = null;
    await Promise.allSettled(
      Object.values(definitions).map((controller) => controller?.dispose?.()),
    );
  }

  return {
    activate,
    dispose,
    getActiveName: () => activeName,
    isCurrentToken: (token) => !disposed && token === activationToken,
  };
}
