import { useEffect, useRef } from "react";
import { useThreatStore } from "../store/threatStore.js";
import { useAuthStore } from "../store/authStore.js";

const WS_BASE = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
const WS_URL = `${WS_BASE}/ws/threat-stream`;
const RECONNECT_DELAY_MS = 3000;

/**
 * useWebSocket — connects to the ThreatScope SOC stream and dispatches
 * incoming events into the Zustand threat store.
 *
 * Handles:
 *   - Automatic reconnection on disconnect (3s backoff)
 *   - Clean teardown on component unmount
 *   - Event routing by event_type
 */
export function useWebSocket() {
  const ws = useRef(null);
  const reconnectTimer = useRef(null);

  const setWsConnected = useThreatStore((s) => s.setWsConnected);
  const handleNewAlert = useThreatStore((s) => s.handleNewAlert);
  const handleSignalPulse = useThreatStore((s) => s.handleSignalPulse);
  const handleNodeStatus = useThreatStore((s) => s.handleNodeStatus);
  const handleMetrics = useThreatStore((s) => s.handleMetrics);
  const token = useAuthStore((s) => s.token);

  const connect = () => {
    if (!token) return;

    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      console.info("[WS] Connected to ThreatScope SOC stream");
      setWsConnected(true);
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        route(msg);
      } catch (e) {
        console.warn("[WS] Malformed message", e);
      }
    };

    ws.current.onclose = () => {
      console.warn("[WS] Disconnected — reconnecting in 3s");
      setWsConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.current.onerror = (err) => {
      console.error("[WS] Error", err);
      ws.current.close();
    };
  };

  const route = (msg) => {
    switch (msg.event_type) {
      case "new_alert":
        handleNewAlert(msg.payload);
        break;
      case "signal_pulse":
        handleSignalPulse(msg.payload);
        break;
      case "node_status":
        handleNodeStatus(msg.payload);
        break;
      case "metrics":
        handleMetrics(msg.payload);
        break;
      case "connected":
        console.info("[WS] Handshake OK:", msg.payload.message);
        break;
      default:
        console.debug("[WS] Unknown event type:", msg.event_type);
    }
  };

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (ws.current) ws.current.close();
    };
  }, [token]);
}
