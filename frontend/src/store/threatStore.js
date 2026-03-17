import { create } from "zustand";

/**
 * Global threat state — updated in real time by the WebSocket hook.
 * All components read from this store; nothing polls the REST API for live data.
 */
export const useThreatStore = create((set, get) => ({
  // Live alert feed (newest first, capped at 200)
  alerts: [],

  // Node status map: { [node_id]: { last_seen, anomaly_score, is_active } }
  nodes: {},

  // Metrics snapshot from the last WebSocket metrics event
  metrics: {
    signals_per_sec: 0,
    alerts_per_min: 0,
    active_nodes: 0,
    ws_connections: 0,
  },

  // Connection health
  wsConnected: false,
  setWsConnected: (v) => set({ wsConnected: v }),

  // ── Event handlers called by useWebSocket hook ──────────────────────────

  handleNewAlert: (payload) => {
    set((state) => ({
      alerts: [
        {
          id: crypto.randomUUID(),
          ...payload,
          received_at: new Date().toISOString(),
        },
        ...state.alerts,
      ].slice(0, 200), // cap at 200
    }));
  },

  handleSignalPulse: (payload) => {
    set((state) => ({
      nodes: {
        ...state.nodes,
        [payload.node_id]: {
          last_seen: payload.timestamp,
          anomaly_score: payload.anomaly_score,
          fingerprint: payload.fingerprint,
          is_active: true,
        },
      },
    }));
  },

  handleNodeStatus: (payload) => {
    set((state) => ({
      nodes: {
        ...state.nodes,
        [payload.node_id]: {
          ...(state.nodes[payload.node_id] || {}),
          ...payload,
        },
      },
    }));
  },

  handleMetrics: (payload) => {
    set({ metrics: payload });
  },

  clearAlerts: () => set({ alerts: [] }),
}));
