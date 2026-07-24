const TOKEN_STORAGE_KEY = "quantvision:lan-access-token";
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

let memoryToken = "";
let promptInProgress = false;

export function isLanBrowserLocation(locationValue = globalThis?.location) {
  const hostname = String(locationValue?.hostname || "").toLowerCase();
  return Boolean(hostname) && !LOOPBACK_HOSTS.has(hostname);
}

export function readLanAccessToken() {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = String(globalThis?.sessionStorage?.getItem(TOKEN_STORAGE_KEY) || "").trim();
  } catch {
    memoryToken = "";
  }
  return memoryToken;
}

export function setLanAccessToken(token) {
  memoryToken = String(token || "").trim();
  try {
    if (memoryToken) globalThis?.sessionStorage?.setItem(TOKEN_STORAGE_KEY, memoryToken);
    else globalThis?.sessionStorage?.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // Session-only memory fallback is sufficient in restricted browsers.
  }
  return memoryToken;
}

export function clearLanAccessToken() {
  setLanAccessToken("");
}

export function requestLanAccessToken() {
  const existing = readLanAccessToken();
  if (existing || !isLanBrowserLocation() || promptInProgress) return existing;
  if (typeof globalThis?.prompt !== "function") return "";
  promptInProgress = true;
  try {
    const provided = globalThis.prompt("此 QuantVision 服務需要 LAN 存取權杖：") || "";
    return setLanAccessToken(provided);
  } finally {
    promptInProgress = false;
  }
}

export function withLanSecurityHeaders(options = {}) {
  const token = readLanAccessToken() || requestLanAccessToken();
  if (!token) return options;
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${token}`);
  headers.set("X-Requested-With", "QuantVision");
  return { ...options, headers };
}

export async function secureFetch(url, options = {}) {
  const response = await fetch(url, withLanSecurityHeaders(options));
  if (response.status !== 401 || !isLanBrowserLocation()) return response;

  clearLanAccessToken();
  const token = requestLanAccessToken();
  if (!token) return response;
  return fetch(url, withLanSecurityHeaders(options));
}

function encodeBase64Url(value) {
  const bytes = new TextEncoder().encode(String(value));
  let binary = "";
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

export function websocketLanProtocols() {
  const token = readLanAccessToken() || requestLanAccessToken();
  return token ? ["qv-access", `qv-token.${encodeBase64Url(token)}`] : [];
}
