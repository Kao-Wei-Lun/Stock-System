export function createLazyDashboardWorkspacePersistence(
  options,
  loadModule = () => import("./dashboardWorkspacePersistence"),
) {
  let controller = null;
  let loadPromise = null;

  async function ensure() {
    if (controller) return controller;
    if (!loadPromise) {
      loadPromise = loadModule()
        .then((module) => {
          controller = module.createDashboardWorkspacePersistence(options);
          return controller;
        })
        .catch((error) => {
          loadPromise = null;
          throw error;
        });
    }
    return loadPromise;
  }

  const action = (key) => async (...args) => (await ensure())[key](...args);

  return {
    deleteWorkspacePreset: action("deleteWorkspacePreset"),
    loadWorkspacePreset: action("loadWorkspacePreset"),
    loadWorkspacePresets: action("loadWorkspacePresets"),
    saveWorkspacePreset: action("saveWorkspacePreset"),
  };
}
