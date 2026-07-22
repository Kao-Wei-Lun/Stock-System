import { ref } from "vue";

const RECONNECT_DELAY_MS = 5000;
const HEARTBEAT_INTERVAL_MS = 15000;
const HEARTBEAT_TIMEOUT_MS = 35000;
const sharedConnectionState = ref(false);

let sharedSocket = null;
let sharedSocketUrl = "";
let reconnectTimer = null;
let heartbeatTimer = null;
let lastServerMessageAt = 0;
let activeConsumers = 0;
let intentionalClose = false;

const messageListeners = new Set();
const subscribedTickers = new Set();

function clearReconnectTimer() {
  if (!reconnectTimer) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
}

function clearHeartbeatTimer() {
  if (!heartbeatTimer) return;
  clearInterval(heartbeatTimer);
  heartbeatTimer = null;
}

function startHeartbeat() {
  clearHeartbeatTimer();
  lastServerMessageAt = Date.now();
  heartbeatTimer = setInterval(() => {
    if (!sharedSocket || sharedSocket.readyState !== 1) return;
    if (Date.now() - lastServerMessageAt > HEARTBEAT_TIMEOUT_MS) {
      sharedSocket.close();
      return;
    }
    sendPayload({ action: "ping" });
  }, HEARTBEAT_INTERVAL_MS);
}

function sendPayload(payload) {
  if (!sharedSocket || sharedSocket.readyState !== 1) return;
  sharedSocket.send(JSON.stringify(payload));
}

function broadcastMessage(message) {
  messageListeners.forEach((listener) => listener(message));
}

function scheduleReconnect() {
  if (reconnectTimer || !sharedSocketUrl || activeConsumers === 0) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    if (activeConsumers > 0) connectSharedSocket();
  }, RECONNECT_DELAY_MS);
}

function handleSocketOpen() {
  clearReconnectTimer();
  sharedConnectionState.value = true;
  startHeartbeat();
  subscribedTickers.forEach((ticker) => {
    sendPayload({ action: "subscribe", ticker });
  });
}

function handleSocketMessage(event) {
  try {
    lastServerMessageAt = Date.now();
    const message = JSON.parse(event.data);
    if (message?.type === "pong") return;
    broadcastMessage(message);
  } catch (error) {
    console.error(error);
  }
}

function handleSocketClose() {
  clearHeartbeatTimer();
  const shouldReconnect = !intentionalClose && activeConsumers > 0;
  intentionalClose = false;
  sharedSocket = null;
  sharedConnectionState.value = false;
  if (shouldReconnect) scheduleReconnect();
}

function connectSharedSocket() {
  if (!sharedSocketUrl) return;
  if (sharedSocket && sharedSocket.readyState < 2) return;
  intentionalClose = false;
  sharedSocket = new WebSocket(sharedSocketUrl);
  sharedSocket.onopen = handleSocketOpen;
  sharedSocket.onmessage = handleSocketMessage;
  sharedSocket.onclose = handleSocketClose;
  sharedSocket.onerror = () => {
    sharedConnectionState.value = false;
  };
}

function releaseSharedSocket() {
  clearReconnectTimer();
  clearHeartbeatTimer();
  subscribedTickers.clear();
  if (sharedSocket && sharedSocket.readyState < 2) {
    intentionalClose = true;
    sharedSocket.close();
    return;
  }
  sharedSocket = null;
  sharedConnectionState.value = false;
}

function shutdownSharedRealtime({ clearListeners = false } = {}) {
  activeConsumers = 0;
  clearReconnectTimer();
  clearHeartbeatTimer();
  subscribedTickers.clear();
  if (clearListeners) messageListeners.clear();
  if (sharedSocket && sharedSocket.readyState < 2) {
    intentionalClose = true;
    sharedSocket.close();
  } else {
    sharedSocket = null;
    intentionalClose = false;
    sharedConnectionState.value = false;
  }
  sharedSocketUrl = "";
}

export function createDashboardRealtime({ wsUrl, onMessage } = {}) {
  let connected = false;

  function connect() {
    if (connected) return;
    connected = true;
    sharedSocketUrl = wsUrl || sharedSocketUrl;
    if (typeof onMessage === "function") {
      messageListeners.add(onMessage);
    }
    activeConsumers += 1;
    connectSharedSocket();
  }

  function disconnect() {
    if (!connected) return;
    connected = false;
    if (typeof onMessage === "function") {
      messageListeners.delete(onMessage);
    }
    activeConsumers = Math.max(0, activeConsumers - 1);
    if (activeConsumers === 0) {
      releaseSharedSocket();
    }
  }

  function subscribeTicker(ticker) {
    if (!ticker) return;
    subscribedTickers.add(ticker);
    sendPayload({ action: "subscribe", ticker });
  }

  function unsubscribeTicker(ticker) {
    if (!ticker) return;
    subscribedTickers.delete(ticker);
    sendPayload({ action: "unsubscribe", ticker });
  }

  return {
    wsConnected: sharedConnectionState,
    connect,
    disconnect,
    send: sendPayload,
    subscribeTicker,
    unsubscribeTicker,
  };
}

export function resetDashboardRealtimeForTests() {
  shutdownSharedRealtime({ clearListeners: true });
}

if (import.meta.hot) {
  import.meta.hot.dispose(() => {
    shutdownSharedRealtime({ clearListeners: true });
  });
}
