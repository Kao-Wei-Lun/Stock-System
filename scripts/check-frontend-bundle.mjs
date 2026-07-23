import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

function readArgument(name, fallback = null) {
  const prefix = `--${name}=`;
  const match = process.argv.find((item) => item.startsWith(prefix));
  return match ? match.slice(prefix.length) : fallback;
}

function resolveManifestEntry(manifest, matcher) {
  return Object.entries(manifest).find(([key, value]) => matcher(key, value)) || null;
}

function collectStaticImports(manifest, startKeys) {
  const visited = new Set();
  const visit = (key) => {
    if (!key || visited.has(key) || !manifest[key]) return;
    visited.add(key);
    for (const dependency of manifest[key].imports || []) visit(dependency);
  };
  startKeys.forEach(visit);
  return visited;
}

function isLegacyEngine(key, value) {
  return key.endsWith("composables/useChartEngine.js")
    || String(value?.file || "").includes("legacy-chart-engine")
    || String(value?.file || "").includes("useChartEngine");
}

function isLwcEngine(key, value) {
  return key.endsWith("composables/useLWCChart.js")
    || String(value?.file || "").includes("lwc-chart-engine")
    || String(value?.file || "").includes("useLWCChart");
}

export function analyzeBundleManifest(manifest, { distDir = null } = {}) {
  const terminalWorkspace = resolveManifestEntry(
    manifest,
    (key) => key.endsWith("components/workspaces/ProChartTerminalWorkspace.vue"),
  );
  const entry = resolveManifestEntry(manifest, (_key, value) => value.isEntry);
  const startKeys = [entry?.[0], terminalWorkspace?.[0]].filter(Boolean);
  const staticKeys = collectStaticImports(manifest, startKeys);
  if (terminalWorkspace) staticKeys.add(terminalWorkspace[0]);

  const files = [...staticKeys]
    .map((key) => manifest[key]?.file)
    .filter(Boolean);
  const legacyEntries = Object.entries(manifest).filter(([key, value]) => isLegacyEngine(key, value));
  const lwcEntries = Object.entries(manifest).filter(([key, value]) => isLwcEngine(key, value));
  const legacyFiles = legacyEntries
    .filter(([key]) => staticKeys.has(key))
    .map(([, value]) => value.file);
  const lwcFiles = lwcEntries
    .filter(([key]) => staticKeys.has(key))
    .map(([, value]) => value.file);
  const gzipSize = (targetFiles) => {
    if (!distDir) return null;
    return targetFiles.reduce((total, file) => {
      const filePath = path.join(distDir, file);
      return fs.existsSync(filePath) ? total + gzipSync(fs.readFileSync(filePath)).length : total;
    }, 0);
  };
  let gzipBytes = null;
  if (distDir) {
    gzipBytes = gzipSize(files);
  }
  const legacyDynamicFiles = legacyEntries.map(([, value]) => value.file).filter((file) => !files.includes(file));
  const lwcDynamicFiles = lwcEntries.map(([, value]) => value.file).filter((file) => !files.includes(file));

  return {
    terminal_workspace_found: Boolean(terminalWorkspace),
    static_files: files,
    static_file_count: files.length,
    static_gzip_bytes: gzipBytes,
    legacy_engine_files: legacyFiles,
    lwc_engine_files: lwcFiles,
    legacy_dynamic_files: legacyDynamicFiles,
    lwc_dynamic_files: lwcDynamicFiles,
    legacy_selected_gzip_bytes: gzipBytes == null ? null : gzipBytes + gzipSize(legacyDynamicFiles),
    lwc_selected_gzip_bytes: gzipBytes == null ? null : gzipBytes + gzipSize(lwcDynamicFiles),
    engines_are_mutually_exclusive: !(legacyFiles.length && lwcFiles.length),
  };
}

const currentFile = fileURLToPath(import.meta.url);
const isDirectRun = process.argv[1] && path.resolve(process.argv[1]) === path.resolve(currentFile);
if (isDirectRun) {
  const repositoryRoot = path.resolve(path.dirname(currentFile), "..");
  const manifestPath = path.resolve(
    readArgument("manifest", path.join(repositoryRoot, "frontend", "dist", ".vite", "manifest.json")),
  );
  const enforce = process.argv.includes("--enforce");
  if (!fs.existsSync(manifestPath)) {
    process.stderr.write(`Bundle manifest not found: ${manifestPath}\n`);
    process.exitCode = 2;
  } else {
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
    const result = analyzeBundleManifest(manifest, {
      distDir: path.resolve(path.dirname(manifestPath), ".."),
    });
    process.stdout.write(`${JSON.stringify({ manifest: manifestPath, enforce, ...result }, null, 2)}\n`);
    if (enforce && !result.engines_are_mutually_exclusive) process.exitCode = 1;
  }
}
