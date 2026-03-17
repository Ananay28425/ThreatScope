import React from "react";
import { useThreatStore } from "../store/threatStore.js";

const severityStyles = {
  CRITICAL: {
    border: "#ef4444",
    bg: "rgba(127, 29, 29, 0.35)",
    text: "#fecaca",
    badge: "#dc2626",
  },
  HIGH: {
    border: "#f97316",
    bg: "rgba(124, 45, 18, 0.35)",
    text: "#fed7aa",
    badge: "#ea580c",
  },
  MEDIUM: {
    border: "#eab308",
    bg: "rgba(113, 63, 18, 0.35)",
    text: "#fde68a",
    badge: "#ca8a04",
  },
  LOW: {
    border: "#38bdf8",
    bg: "rgba(12, 74, 110, 0.35)",
    text: "#bae6fd",
    badge: "#0284c7",
  },
  DEFAULT: {
    border: "#475569",
    bg: "rgba(30, 41, 59, 0.35)",
    text: "#cbd5e1",
    badge: "#475569",
  },
};

function formatTimestamp(value) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Invalid timestamp";
  return date.toLocaleString();
}

function formatFingerprint(value) {
  if (!value) return "Unclassified activity";
  return value.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase());
}

function AlertCard({ alert }) {
  const styles = severityStyles[alert.severity] || severityStyles.DEFAULT;
  const nodeCount =
    alert.node_count ??
    (Array.isArray(alert.contributing_nodes) ? alert.contributing_nodes.length : 0);

  return (
    <div
      style={{
        background: styles.bg,
        border: `1px solid ${styles.border}`,
        borderLeft: `4px solid ${styles.border}`,
        borderRadius: "12px",
        padding: "14px",
        display: "flex",
        flexDirection: "column",
        gap: "10px",
        boxShadow: "0 6px 18px rgba(0, 0, 0, 0.18)",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "10px",
        }}
      >
        <div>
          <div
            style={{
              color: styles.text,
              fontSize: "15px",
              fontWeight: 700,
              marginBottom: "4px",
            }}
          >
            {formatFingerprint(alert.fingerprint)}
          </div>
          <div
            style={{
              color: "#94a3b8",
              fontSize: "12px",
            }}
          >
            {formatTimestamp(alert.received_at || alert.timestamp || alert.created_at)}
          </div>
        </div>

        <span
          style={{
            background: styles.badge,
            color: "#fff",
            fontSize: "11px",
            fontWeight: 700,
            padding: "4px 8px",
            borderRadius: "999px",
            letterSpacing: "0.04em",
          }}
        >
          {alert.severity || "UNKNOWN"}
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
          gap: "10px",
        }}
      >
        <div>
          <div style={{ color: "#64748b", fontSize: "11px", textTransform: "uppercase" }}>
            Score
          </div>
          <div style={{ color: "#e2e8f0", fontSize: "14px", fontWeight: 600 }}>
            {typeof alert.anomaly_score === "number"
              ? alert.anomaly_score.toFixed(3)
              : "N/A"}
          </div>
        </div>

        <div>
          <div style={{ color: "#64748b", fontSize: "11px", textTransform: "uppercase" }}>
            Nodes
          </div>
          <div style={{ color: "#e2e8f0", fontSize: "14px", fontWeight: 600 }}>
            {nodeCount}
          </div>
        </div>
      </div>

      {Array.isArray(alert.contributing_nodes) && alert.contributing_nodes.length > 0 && (
        <div>
          <div
            style={{
              color: "#64748b",
              fontSize: "11px",
              textTransform: "uppercase",
              marginBottom: "6px",
            }}
          >
            Contributing Nodes
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: "6px",
            }}
          >
            {alert.contributing_nodes.map((nodeId) => (
              <span
                key={nodeId}
                style={{
                  background: "rgba(15, 23, 42, 0.6)",
                  color: "#cbd5e1",
                  border: "1px solid rgba(148, 163, 184, 0.25)",
                  borderRadius: "999px",
                  padding: "4px 8px",
                  fontSize: "11px",
                }}
              >
                {nodeId}
              </span>
            ))}
          </div>
        </div>
      )}

      {alert.description && (
        <div
          style={{
            color: "#cbd5e1",
            fontSize: "13px",
            lineHeight: 1.5,
          }}
        >
          {alert.description}
        </div>
      )}
    </div>
  );
}

export default function AlertsPanel() {
  const alerts = useThreatStore((state) => state.alerts);

  return (
    <section
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        background:
          "linear-gradient(180deg, rgba(15,23,42,0.92) 0%, rgba(2,6,23,0.96) 100%)",
        border: "1px solid rgba(51, 65, 85, 0.65)",
        borderRadius: "16px",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "16px 18px",
          borderBottom: "1px solid rgba(51, 65, 85, 0.65)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div>
          <h2
            style={{
              margin: 0,
              color: "#f8fafc",
              fontSize: "16px",
              fontWeight: 700,
            }}
          >
            Alerts Panel
          </h2>
          <p
            style={{
              margin: "4px 0 0",
              color: "#94a3b8",
              fontSize: "12px",
            }}
          >
            Live correlated alerts from the ThreatScope backend
          </p>
        </div>

        <div
          style={{
            minWidth: "34px",
            height: "34px",
            borderRadius: "999px",
            display: "grid",
            placeItems: "center",
            background: alerts.length ? "rgba(220, 38, 38, 0.18)" : "rgba(71, 85, 105, 0.18)",
            color: alerts.length ? "#fecaca" : "#cbd5e1",
            border: `1px solid ${
              alerts.length ? "rgba(220, 38, 38, 0.4)" : "rgba(71, 85, 105, 0.4)"
            }`,
            fontSize: "13px",
            fontWeight: 700,
          }}
        >
          {alerts.length}
        </div>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
        }}
      >
        {alerts.length === 0 ? (
          <div
            style={{
              flex: 1,
              minHeight: "220px",
              display: "grid",
              placeItems: "center",
              textAlign: "center",
              color: "#94a3b8",
              border: "1px dashed rgba(71, 85, 105, 0.6)",
              borderRadius: "14px",
              background: "rgba(15, 23, 42, 0.35)",
              padding: "24px",
            }}
          >
            <div>
              <div
                style={{
                  color: "#e2e8f0",
                  fontSize: "15px",
                  fontWeight: 600,
                  marginBottom: "6px",
                }}
              >
                No alerts yet
              </div>
              <div style={{ fontSize: "13px", lineHeight: 1.6 }}>
                The system is connected and waiting for correlated threat activity.
              </div>
            </div>
          </div>
        ) : (
          alerts.map((alert) => (
            <AlertCard
              key={alert.id || `${alert.fingerprint}-${alert.received_at || Math.random()}`}
              alert={alert}
            />
          ))
        )}
      </div>
    </section>
  );
}
