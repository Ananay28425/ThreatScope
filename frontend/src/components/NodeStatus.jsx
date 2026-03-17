/**
 * NodeStatus — sidebar panel showing the current state of all simulated nodes.
 * Colour-coded by anomaly score, updated in real time via WebSocket signal_pulse events.
 */

import { useThreatStore } from "../store/threatStore.js";
import { formatDistanceToNow } from "date-fns";

function scoreColor(score) {
  if (!score && score !== 0) return "#334155";
  if (score >= 0.80) return "#ff2244";
  if (score >= 0.50) return "#ffa500";
  return "#22c55e";
}

function NodeRow({ nodeId, state }) {
  const color = scoreColor(state?.anomaly_score);
  const score = state?.anomaly_score;
  const lastSeen = state?.last_seen ? new Date(state.last_seen) : null;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      padding: "8px 10px",
      borderRadius: "5px",
      marginBottom: "4px",
      background: "#080f1a",
      borderLeft: `2px solid ${color}`,
    }}>
      {/* Status dot */}
      <div style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: state?.is_active ? color : "#334155",
        boxShadow: state?.is_active ? `0 0 5px ${color}` : "none",
        marginRight: 10,
        flexShrink: 0,
      }} />

      {/* Node ID */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: "12px", fontWeight: 600, color: "#e2e8f0", fontFamily: "monospace" }}>
          {nodeId}
        </div>
        {lastSeen && (
          <div style={{ fontSize: "10px", color: "#475569", marginTop: 1 }}>
            {formatDistanceToNow(lastSeen, { addSuffix: true })}
          </div>
        )}
      </div>

      {/* Score */}
      <div style={{
        fontSize: "12px",
        fontWeight: 700,
        color,
        fontFamily: "monospace",
        fontVariantNumeric: "tabular-nums",
      }}>
        {score != null ? score.toFixed(2) : "—"}
      </div>
    </div>
  );
}

export default function NodeStatus() {
  const nodes = useThreatStore((s) => s.nodes);
  const entries = Object.entries(nodes).sort((a, b) =>
    (b[1].anomaly_score ?? 0) - (a[1].anomaly_score ?? 0)
  );

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <h2 style={{
        fontSize: "13px",
        fontWeight: 600,
        color: "#94a3b8",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        padding: "12px 0",
        borderBottom: "1px solid #1e293b",
        marginBottom: "10px",
      }}>
        Node Status
        <span style={{ float: "right", color: "#22c55e", fontVariantNumeric: "tabular-nums" }}>
          {entries.filter(([, s]) => s.is_active).length} active
        </span>
      </h2>

      <div style={{ flex: 1, overflowY: "auto" }}>
        {entries.length === 0 ? (
          <div style={{ color: "#334155", fontSize: "12px", textAlign: "center", marginTop: "30px" }}>
            Waiting for nodes…
          </div>
        ) : (
          entries.map(([nodeId, state]) => (
            <NodeRow key={nodeId} nodeId={nodeId} state={state} />
          ))
        )}
      </div>
    </div>
  );
}
