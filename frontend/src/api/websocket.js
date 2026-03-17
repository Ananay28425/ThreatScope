const DEFAULT_PROTOCOL = window.location.protocol === "https:" ? "wss:" : "ws:";
const DEFAULT_HOST = window.location.host;
const DEFAULT_BASE = `${DEFAULT_PROTOCOL}//${DEFAULT_HOST}`;
const WS_BASE_URL = (import.meta.env.VITE_WS_URL || DEFAULT_BASE).replace(/\/+$/, "");
const THREAT_STREAM_PATH = "/ws/threat-stream";

export function buildThreatStreamUrl(path = THREAT_STREAM_PATH) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${WS_BASE_URL}${normalizedPath}`;
}

export class ThreatScopeWebSocketClient {
  constructor({
    url = buildThreatStreamUrl(),
    protocols,
    onOpen,
    onClose,
    onError,
    onMessage,
    autoReconnect = true,
    reconnectDelayMs = 3000,
    maxReconnectDelayMs = 30000,
  } = {}) {
    this.url = url;
    this.protocols = protocols;
    this.onOpen = onOpen;
    this.onClose = onClose;
    this.onError = onError;
    this.onMessage = onMessage;
    this.autoReconnect = autoReconnect;
    this.reconnectDelayMs = reconnectDelayMs;
    this.maxReconnectDelayMs = maxReconnectDelayMs;

    this.socket = null;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.manuallyClosed = false;
  }

  connect() {
    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return this.socket;
    }

    this.manuallyClosed = false;
    this.socket = this.protocols
      ? new WebSocket(this.url, this.protocols)
      : new WebSocket(this.url);

    this.socket.onopen = (event) => {
      this.reconnectAttempts = 0;
      if (typeof this.onOpen === "function") {
        this.onOpen(event);
      }
    };

    this.socket.onmessage = (event) => {
      const parsed = this.parseMessage(event.data);

      if (typeof this.onMessage === "function") {
        this.onMessage(parsed, event);
      }
    };

    this.socket.onerror = (event) => {
      if (typeof this.onError === "function") {
        this.onError(event);
      }
    };

    this.socket.onclose = (event) => {
      if (typeof this.onClose === "function") {
        this.onClose(event);
      }

      if (!this.manuallyClosed && this.autoReconnect) {
        this.scheduleReconnect();
      }
    };

    return this.socket;
  }

  disconnect(code = 1000, reason = "Client disconnected") {
    this.manuallyClosed = true;
    this.clearReconnectTimer();

    if (this.socket) {
      this.socket.close(code, reason);
    }
  }

  send(data) {
    if (!this.isOpen()) {
      throw new Error("WebSocket is not open");
    }

    const payload = typeof data === "string" ? data : JSON.stringify(data);
    this.socket.send(payload);
  }

  isOpen() {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  parseMessage(data) {
    if (typeof data !== "string") {
      return data;
    }

    try {
      return JSON.parse(data);
    } catch {
      return data;
    }
  }

  scheduleReconnect() {
    this.clearReconnectTimer();

    const delay = Math.min(
      this.reconnectDelayMs * 2 ** this.reconnectAttempts,
      this.maxReconnectDelayMs
    );

    this.reconnectAttempts += 1;
    this.reconnectTimer = window.setTimeout(() => {
      this.connect();
    }, delay);
  }

  clearReconnectTimer() {
    if (this.reconnectTimer) {
      window.clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

export function createThreatStreamClient(options = {}) {
  return new ThreatScopeWebSocketClient({
    url: buildThreatStreamUrl(),
    ...options,
  });
}

export default createThreatStreamClient;
