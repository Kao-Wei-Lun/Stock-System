const LEGACY_STYLE_ID = "qv-legacy-dashboard-style";
const LEGACY_SCRIPT_ID = "qv-legacy-dashboard-script";
const LEGACY_FETCH_ERROR = `
  <div class="legacy-error">
    <div class="legacy-card">
      <h1>前端載入失敗</h1>
      <p>Vue 3 啟動成功，但舊版 dashboard 內容沒有成功載入。請確認 <code>legacy-dashboard.html</code> 存在，或把錯誤訊息貼給我。</p>
    </div>
  </div>
`;

let mountedRoot = null;

const LEGACY_CONFIG_BLOCK = [
  "const IS_FILE_ORIGIN = window.location.protocol === 'file:';",
  "const API = IS_FILE_ORIGIN ? 'http://localhost:8001' : window.location.origin;",
  "const WS_URL = (IS_FILE_ORIGIN",
  "  ? 'ws://localhost:8001'",
  "  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`) + '/ws';",
].join("\n");

const LEGACY_RUNTIME_CONFIG = [
  "const API = window.__QV_API_BASE__ || 'http://localhost:8001';",
  "const WS_URL = `${(window.__QV_WS_BASE__ || 'ws://localhost:8001').replace(/\\/$/, '')}/ws`;",
].join("\n");

function getLegacyHtmlUrl() {
  return new URL(`${import.meta.env.BASE_URL}legacy-dashboard.html`, window.location.origin).toString();
}

function getApiBase() {
  if (import.meta.env.DEV) {
    return (import.meta.env.VITE_API_BASE || "http://localhost:8001").replace(/\/$/, "");
  }
  return window.location.origin;
}

function getWsBase() {
  if (import.meta.env.DEV) {
    return (import.meta.env.VITE_WS_BASE || "ws://localhost:8001").replace(/\/$/, "");
  }
  return `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
}

function ensureLegacyStyle(styleText) {
  let styleEl = document.getElementById(LEGACY_STYLE_ID);
  if (!styleEl) {
    styleEl = document.createElement("style");
    styleEl.id = LEGACY_STYLE_ID;
    document.head.appendChild(styleEl);
  }
  styleEl.textContent = styleText;
}

function transformLegacyScript(scriptText) {
  return scriptText
    .replace(
      LEGACY_CONFIG_BLOCK,
      LEGACY_RUNTIME_CONFIG,
    )
    .replace("let ws = null;", "let ws = null;\nwindow.__QV_GET_WS__ = () => ws;")
    .replace(/window\.addEventListener\('load', async \(\) => \{/, "(async () => {")
    .replace(/\}\);\s*$/, "})();");
}

function executeLegacyScript(scriptText) {
  const oldScript = document.getElementById(LEGACY_SCRIPT_ID);
  if (oldScript) {
    oldScript.remove();
  }

  const scriptEl = document.createElement("script");
  scriptEl.id = LEGACY_SCRIPT_ID;
  scriptEl.textContent = scriptText;
  document.body.appendChild(scriptEl);
}

export async function mountLegacyDashboard(root) {
  unmountLegacyDashboard();
  mountedRoot = root;

  if (!root) {
    return;
  }

  root.innerHTML = `
    <div class="legacy-loading">
      <div class="legacy-card">
        <h1>載入 QuantVision Vue 3 前端...</h1>
        <p>正在載入原有 dashboard 內容與資料同步邏輯。</p>
      </div>
    </div>
  `;

  try {
    const response = await fetch(getLegacyHtmlUrl(), { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to fetch legacy dashboard: ${response.status}`);
    }

    const rawHtml = await response.text();
    const doc = new DOMParser().parseFromString(rawHtml, "text/html");
    const styleText = Array.from(doc.querySelectorAll("style"))
      .map((node) => node.textContent || "")
      .join("\n");
    const scriptText = Array.from(doc.querySelectorAll("script"))
      .map((node) => node.textContent || "")
      .join("\n");

    doc.querySelectorAll("script").forEach((node) => node.remove());
    ensureLegacyStyle(styleText);

    window.__QV_API_BASE__ = getApiBase();
    window.__QV_WS_BASE__ = getWsBase();

    root.innerHTML = doc.body.innerHTML;
    executeLegacyScript(transformLegacyScript(scriptText));
  } catch (error) {
    console.error(error);
    root.innerHTML = LEGACY_FETCH_ERROR;
  }
}

export function unmountLegacyDashboard() {
  const ws = typeof window.__QV_GET_WS__ === "function" ? window.__QV_GET_WS__() : null;
  if (ws && ws.readyState < 2) {
    ws.close();
  }

  const scriptEl = document.getElementById(LEGACY_SCRIPT_ID);
  if (scriptEl) {
    scriptEl.remove();
  }

  if (mountedRoot) {
    mountedRoot.innerHTML = "";
  }

  delete window.__QV_API_BASE__;
  delete window.__QV_WS_BASE__;
  delete window.__QV_GET_WS__;
}
