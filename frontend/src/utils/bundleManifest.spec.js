import { describe, expect, it } from "vitest";

import {
  analyzeBundleManifest,
  evaluateBundleBudgets,
} from "../../../scripts/check-frontend-bundle.mjs";


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
    expect(result.legacy_dynamic_files).toEqual(["assets/legacy-chart-engine.js"]);
    expect(result.lwc_dynamic_files).toEqual(["assets/lwc-chart-engine.js"]);
  });

  it("enforces initial payload and request-count budgets", () => {
    const budget = evaluateBundleBudgets({
      terminal_workspace_found: true,
      engines_are_mutually_exclusive: true,
      static_gzip_bytes: 120_000,
      legacy_selected_gzip_bytes: 180_000,
      lwc_selected_gzip_bytes: 188_300,
      static_file_count: 4,
    });

    expect(budget.passed).toBe(true);
    expect(budget.limits.max_selected_gzip_bytes).toBe(190_000);
  });

  it("fails when either selectable engine exceeds the delivery budget", () => {
    const budget = evaluateBundleBudgets({
      terminal_workspace_found: true,
      engines_are_mutually_exclusive: true,
      static_gzip_bytes: 120_000,
      legacy_selected_gzip_bytes: 180_000,
      lwc_selected_gzip_bytes: 190_001,
      static_file_count: 4,
    });

    expect(budget.passed).toBe(false);
    expect(budget.checks.lwc_selected_gzip_bytes).toBe(false);
  });

  it("fails closed when gzip measurements are unavailable", () => {
    const budget = evaluateBundleBudgets({
      terminal_workspace_found: true,
      engines_are_mutually_exclusive: true,
      static_gzip_bytes: null,
      legacy_selected_gzip_bytes: null,
      lwc_selected_gzip_bytes: null,
      static_file_count: 4,
    });

    expect(budget.passed).toBe(false);
    expect(budget.checks.static_gzip_bytes).toBe(false);
  });
});
