import { describe, expect, it } from "vitest";

import { analyzeBundleManifest } from "../../../scripts/check-frontend-bundle.mjs";


describe("bundle manifest performance gate", () => {
  it("detects when both chart engines are static terminal dependencies", () => {
    const manifest = {
      "index.html": {
        file: "assets/index.js",
        isEntry: true,
        imports: ["_legacy.js"],
      },
      "_legacy.js": { file: "assets/legacy-chart-engine.js" },
      "_lwc.js": { file: "assets/lwc-chart-engine.js" },
      "src/components/workspaces/ProChartTerminalWorkspace.vue": {
        file: "assets/terminal.js",
        imports: ["index.html", "_legacy.js", "_lwc.js"],
      },
    };

    const result = analyzeBundleManifest(manifest);

    expect(result.engines_are_mutually_exclusive).toBe(false);
    expect(result.legacy_engine_files).toHaveLength(1);
    expect(result.lwc_engine_files).toHaveLength(1);
  });

  it("passes when chart engines remain dynamic and outside the static graph", () => {
    const manifest = {
      "index.html": {
        file: "assets/index.js",
        isEntry: true,
        imports: ["_vendor.js"],
      },
      "_vendor.js": { file: "assets/vendor.js" },
      "_legacy.js": { file: "assets/legacy-chart-engine.js" },
      "_lwc.js": { file: "assets/lwc-chart-engine.js" },
      "src/components/workspaces/ProChartTerminalWorkspace.vue": {
        file: "assets/terminal.js",
        imports: ["index.html"],
        dynamicImports: ["_legacy.js", "_lwc.js"],
      },
    };

    const result = analyzeBundleManifest(manifest);

    expect(result.engines_are_mutually_exclusive).toBe(true);
    expect(result.legacy_engine_files).toEqual([]);
    expect(result.lwc_engine_files).toEqual([]);
  });
});
