import { ref } from "vue";

const RECONNECT_DELAY_MS = 5000;
const sharedConnectionState = ref(false);

let sharedSocket = null;
let sharedSocketUrl = "";
let reconnectTimer = null;
let activeConsumers = 0;
let intentionalClose = false;

const messageListeners = new Set();
const subscribedTickers = new Set();

function clearReconnectTimer() {
  if (!reconnectTimer) return;
  clearTimeout(reconnectTimer);
  reconnectTimer = null;
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
  subscribedTickers.forEach((ticker) => {
    sendPayload({ action: "subscribe", ticker });
  });
}

function handleSocketMessage(event) {
  try {
    broadcastMessage(JSON.parse(event.data));
  } catch (error) {
    console.error(error);
  }
}

function handleSocketClose() {
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
