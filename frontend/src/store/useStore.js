import { create } from "zustand";

/**
 * ThreatScope unified frontend store.
 *
 * This store centralizes:
 * - auth/session state
 * - websocket connection state
 * - live alerts
 * - node status / pulses
 * - dashboard metrics
 * - lightweight UI state
 *
 * It is intentionally self-contained so components can import one hook:
 *   import { useStore } from "./store/useStore";
 */

const MAX_ALERTS = 200;
const ALERT_STATUSES = ["open", "investigating", "resolved"];
const ALERT_SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

const defaultMetrics = {
  signals_per_sec: 0,
  alerts_per_min: 0,
  active_nodes: 0,
  ws_connections: 0,
};

const defaultUi = {
  selectedAlertId: null,
  selectedNodeId: null,
  sidebarOpen: true,
  theme: "dark",
};

function nowIso() {
  return new Date().toISOString();
}

function normalizeSeverity(value) {
  const normalized = String(value || "LOW").toUpperCase();
  return ALERT_SEVERITIES.includes(normalized) ? normalized : "LOW";
}

function normalizeStatus(value) {
  const normalized = String(value || "open").toLowerCase();
  return ALERT_STATUSES.includes(normalized) ? normalized : "open";
}

function safeArray(value) {
  return Array.isArray(value) ? value : [];
}

function createAlertId(payload) {
  if (payload?.id) return String(payload.id);
  if (payload?.alert_id) return String(payload.alert_id);

  const fingerprint = payload?.fingerprint || "alert";
  const ts = payload?.timestamp || payload?.received_at || Date.now();
  return `${fingerprint}-${ts}-${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeAlert(payload = {}) {
  return {
    id: createAlertId(payload),
    severity: normalizeSeverity(payload.severity),
    fingerprint: payload.fingerprint ?? null,
    description: payload.description ?? null,
    anomaly_score: Number(payload.anomaly_score ?? 0),
    node_count:
      Number(payload.node_count) ||
      safeArray(payload.contributing_nodes).length ||
      0,
    contributing_nodes: safeArray(payload.contributing_nodes),
    status: normalizeStatus(payload.status),
    timestamp: payload.timestamp ?? nowIso(),
    received_at: payload.received_at ?? nowIso(),
    recommended_action: payload.recommended_action ?? null,
    mitre_attack: safeArray(payload.mitre_attack),
    regions: safeArray(payload.regions),
  };
}

function normalizeNode(nodeId, payload = {}, existing = {}) {
  return {
    node_id: nodeId,
    is_active: payload.is_active ?? existing.is_active ?? true,
    last_seen: payload.last_seen ?? payload.timestamp ?? existing.last_seen ?? nowIso(),
    anomaly_score: Number(payload.anomaly_score ?? existing.anomaly_score ?? 0),
    fingerprint: payload.fingerprint ?? existing.fingerprint ?? null,
    confidence: Number(payload.confidence ?? existing.confidence ?? 0),
    region: payload.region ?? existing.region ?? null,
    latitude:
      payload.latitude ?? existing.latitude ?? null,
    longitude:
      payload.longitude ?? existing.longitude ?? null,
    pulses: Number(payload.pulses ?? existing.pulses ?? 0),
  };
}

export const useStore = create((set, get) => ({
  // ── Auth ────────────────────────────────────────────────────────────────
  token: null,
  refreshToken: null,
  user: null,
  isAuthenticated: false,

  setAuth: ({ token = null, refreshToken = null, user = null } = {}) =>
    set({
      token,
      refreshToken,
      user,
      isAuthenticated: Boolean(token),
    }),

  clearAuth: () =>
    set({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
    }),

  // ── Connection state ────────────────────────────────────────────────────
  wsConnected: false,
  lastWsMessageAt: null,

  setWsConnected: (connected) =>
    set({
      wsConnected: Boolean(connected),
      lastWsMessageAt: connected ? nowIso() : get().lastWsMessageAt,
    }),

  markWsMessageReceived: () =>
    set({
      lastWsMessageAt: nowIso(),
    }),

  // ── Dashboard data ──────────────────────────────────────────────────────
  alerts: [],
  nodes: {},
  metrics: defaultMetrics,

  addAlert: (payload) =>
    set((state) => {
      const alert = normalizeAlert(payload);
      const deduped = state.alerts.filter((item) => item.id !== alert.id);

      return {
        alerts: [alert, ...deduped].slice(0, MAX_ALERTS),
      };
    }),

  setAlerts: (alerts) =>
    set({
      alerts: safeArray(alerts).map(normalizeAlert).slice(0, MAX_ALERTS),
    }),

  updateAlertStatus: (alertId, status) =>
    set((state) => ({
      alerts: state.alerts.map((alert) =>
        alert.id === alertId
          ? {
              ...alert,
              status: normalizeStatus(status),
            }
          : alert
      ),
    })),

  clearAlerts: () => set({ alerts: [] }),

  upsertNode: (nodeId, payload = {}) =>
    set((state) => ({
      nodes: {
        ...state.nodes,
        [nodeId]: normalizeNode(nodeId, payload, state.nodes[nodeId]),
      },
    })),

  setNodes: (nodes) => {
    if (Array.isArray(nodes)) {
      const mapped = {};
      for (const item of nodes) {
        const nodeId = item?.node_id || item?.id || item?.name;
        if (!nodeId) continue;
        mapped[nodeId] = normalizeNode(nodeId, item);
      }
      return set({ nodes: mapped });
    }

    if (nodes && typeof nodes === "object") {
      const mapped = {};
      for (const [nodeId, payload] of Object.entries(nodes)) {
        mapped[nodeId] = normalizeNode(nodeId, payload);
      }
      return set({ nodes: mapped });
    }

    set({ nodes: {} });
  },

  handleSignalPulse: (payload = {}) =>
    set((state) => {
      const nodeId = payload.node_id || "unknown";
      const existing = state.nodes[nodeId] || {};
      const next = normalizeNode(
        nodeId,
        {
          ...payload,
          is_active: true,
          pulses: Number(existing.pulses ?? 0) + 1,
          last_seen: payload.timestamp ?? nowIso(),
        },
        existing
      );

      return {
        nodes: {
          ...state.nodes,
          [nodeId]: next,
        },
        lastWsMessageAt: nowIso(),
      };
    }),

  handleNodeStatus: (payload = {}) =>
    set((state) => {
      const nodeId = payload.node_id || payload.id || "unknown";
      return {
        nodes: {
          ...state.nodes,
          [nodeId]: normalizeNode(nodeId, payload, state.nodes[nodeId]),
        },
        lastWsMessageAt: nowIso(),
      };
    }),

  handleMetrics: (payload = {}) =>
    set({
      metrics: {
        ...defaultMetrics,
        ...payload,
      },
      lastWsMessageAt: nowIso(),
    }),

  handleNewAlert: (payload = {}) => {
    get().addAlert(payload);
    set({ lastWsMessageAt: nowIso() });
  },

  // ── Unified websocket event router ──────────────────────────────────────
  routeEvent: (message = {}) => {
    const { event_type, payload } = message;

    switch (event_type) {
      case "new_alert":
        get().handleNewAlert(payload);
        break;
      case "signal_pulse":
        get().handleSignalPulse(payload);
        break;
      case "node_status":
        get().handleNodeStatus(payload);
        break;
      case "metrics":
        get().handleMetrics(payload);
        break;
      case "connected":
        set({
          wsConnected: true,
          lastWsMessageAt: nowIso(),
        });
        break;
      default:
        set({ lastWsMessageAt: nowIso() });
        break;
    }
  },

  // ── UI state ────────────────────────────────────────────────────────────
  ui: defaultUi,

  setSelectedAlertId: (selectedAlertId) =>
    set((state) => ({
      ui: {
        ...state.ui,
        selectedAlertId,
      },
    })),

  setSelectedNodeId: (selectedNodeId) =>
    set((state) => ({
      ui: {
        ...state.ui,
        selectedNodeId,
      },
    })),

  setSidebarOpen: (sidebarOpen) =>
    set((state) => ({
      ui: {
        ...state.ui,
        sidebarOpen: Boolean(sidebarOpen),
      },
    })),

  setTheme: (theme) =>
    set((state) => ({
      ui: {
        ...state.ui,
        theme: theme || "dark",
      },
    })),

  resetUi: () =>
    set((state) => ({
      ui: {
        ...defaultUi,
        theme: state.ui.theme || "dark",
      },
    })),

  // ── Derived selectors/helpers as callable state methods ─────────────────
  getActiveNodes: () => {
    const nodes = Object.values(get().nodes);
    return nodes.filter((node) => node.is_active);
  },

  getNodeCount: () => Object.keys(get().nodes).length,

  getOpenAlerts: () => get().alerts.filter((alert) => alert.status === "open"),

  getAlertsBySeverity: (severity) => {
    const normalized = normalizeSeverity(severity);
    return get().alerts.filter((alert) => alert.severity === normalized);
  },

  resetDashboardState: () =>
    set({
      alerts: [],
      nodes: {},
      metrics: defaultMetrics,
      wsConnected: false,
      lastWsMessageAt: null,
    }),

  resetAll: () =>
    set({
      token: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      wsConnected: false,
      lastWsMessageAt: null,
      alerts: [],
      nodes: {},
      metrics: defaultMetrics,
      ui: defaultUi,
    }),
}));

export default useStore;
