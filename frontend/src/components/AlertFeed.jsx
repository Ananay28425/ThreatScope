/**
 * AlertFeed — live scrolling list of correlation engine alerts.
 *
 * Populated entirely from the Zustand threat store (WebSocket-driven).
 * No REST polling — alerts appear in real time as the engine fires them.
 */

import { motion, AnimatePresence } from "framer-motion";
import { useThreatStore } from "../store/threatStore.js";
import { formatDistanceToNow } from "date-fns";

const SEVERITY_STYLES = {
  CRITICAL: { border: "#ff2244", bg: "#1a0008", badge: "#ff2244", text: "#ff6680" },
  HIGH:     { border: "#ff6600", bg: "#1a0a00", badge: "#ff6600", text: "#ffaa44" },
  MEDIUM:   { border: "#ffa500", bg: "#1a1200", badge: "#ffa500", text: "#ffc844" },
  LOW:      { border: "#00bfff", bg: "#001a22", badge: "#00bfff", text: "#44d4ff" },
};

function AlertCard({ alert }) {
  const styles = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.LOW;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -12, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      style={{
        borderLeft: `3px solid ${styles.border}`,
        background: styles.bg,
        borderRadius: "6px",
        padding: "10px 14px",
        marginBottom: "8px",
        fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
        fontSize: "12px",
      }}
    >
      {/* Header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <span style={{
          background: styles.badge,
          color: "#fff",
          padding: "2px 7px",
          borderRadius: "3px",
          fontSize: "10px",
          fontWeight: 700,
          letterSpacing: "0.05em",
        }}>
          {alert.severity}
        </span>
        <span style={{ color: "#64748b", fontSize: "10px" }}>
          {formatDistanceToNow(new Date(alert.received_at), { addSuffix: true })}
        </span>
      </div>

      {/* Fingerprint */}
      {alert.fingerprint && (
        <div style={{ color: styles.text, fontWeight: 600, marginBottom: 4 }}>
          {alert.fingerprint.replace(/_/g, " ")}
        </div>
      )}

      {/* Stats */}
      <div style={{ color: "#94a3b8", fontSize: "11px" }}>
        <span style={{ marginRight: 12 }}>
          Score: <b style={{ color: "#e2e8f0" }}>{(alert.anomaly_score ?? 0).toFixed(2)}</b>
        </span>
        <span>
          Nodes: <b style={{ color: "#e2e8f0" }}>{alert.node_count ?? (alert.contributing_nodes?.length ?? "—")}</b>
        </span>
      </div>
    </motion.div>
  );
}

export default function AlertFeed() {
  const alerts = useThreatStore((s) => s.alerts);

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "12px 0",
        borderBottom: "1px solid #1e293b",
        marginBottom: "12px",
      }}>
        <h2 style={{ fontSize: "13px", fontWeight: 600, color: "#94a3b8", letterSpacing: "0.1em", textTransform: "uppercase" }}>
          Live Alert Feed
        </h2>
        <span style={{
          background: alerts.length > 0 ? "#ff2244" : "#1e293b",
          color: "#fff",
          borderRadius: "10px",
          padding: "2px 8px",
          fontSize: "11px",
          fontWeight: 700,
          minWidth: "24px",
          textAlign: "center",
        }}>
          {alerts.length}
        </span>
      </div>

      {/* Feed */}
      <div style={{ flex: 1, overflowY: "auto", paddingRight: "4px" }}>
        {alerts.length === 0 ? (
          <div style={{ color: "#334155", fontSize: "13px", textAlign: "center", marginTop: "40px" }}>
            No alerts yet. Monitoring active.
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {alerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
