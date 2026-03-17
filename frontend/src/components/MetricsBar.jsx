/**
 * MetricsBar — top status bar showing live system metrics.
 * Updated in real time from the WebSocket metrics events.
 */

import { useThreatStore } from "../store/threatStore.js";

function Metric({ label, value, unit = "", color = "#00bfff" }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "0 24px",
      borderRight: "1px solid #1e293b",
    }}>
      <span style={{ fontSize: "20px", fontWeight: 700, color, fontVariantNumeric: "tabular-nums" }}>
        {value}
        {unit && <span style={{ fontSize: "12px", marginLeft: 2, opacity: 0.7 }}>{unit}</span>}
      </span>
      <span style={{ fontSize: "10px", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 2 }}>
        {label}
      </span>
    </div>
  );
}

function StatusDot({ connected }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 24px" }}>
      <div style={{
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: connected ? "#22c55e" : "#ff2244",
        boxShadow: connected ? "0 0 6px #22c55e" : "0 0 6px #ff2244",
      }} />
      <span style={{ fontSize: "11px", color: connected ? "#22c55e" : "#ff6680" }}>
        {connected ? "SOC LIVE" : "RECONNECTING"}
      </span>
    </div>
  );
}

export default function MetricsBar() {
  const metrics     = useThreatStore((s) => s.metrics);
  const alerts      = useThreatStore((s) => s.alerts);
  const wsConnected = useThreatStore((s) => s.wsConnected);
  const nodes       = useThreatStore((s) => s.nodes);

  const activeNodes   = Object.values(nodes).filter((n) => n.is_active).length;
  const criticalCount = alerts.filter((a) => a.severity === "CRITICAL").length;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      height: "56px",
      background: "#070d16",
      borderBottom: "1px solid #0f2035",
      paddingLeft: "16px",
      overflow: "hidden",
    }}>
      {/* Branding */}
      <div style={{ padding: "0 24px 0 8px", borderRight: "1px solid #1e293b" }}>
        <span style={{ fontSize: "15px", fontWeight: 800, color: "#00bfff", letterSpacing: "0.06em" }}>
          THREAT<span style={{ color: "#ff2244" }}>SCOPE</span>
        </span>
      </div>

      <StatusDot connected={wsConnected} />

      <Metric label="Signals/sec"  value={metrics.signals_per_sec?.toFixed(1) ?? "—"} />
      <Metric label="Active Nodes" value={activeNodes} color="#22c55e" />
      <Metric label="Total Alerts" value={alerts.length} color="#ffa500" />
      <Metric label="Critical"     value={criticalCount} color="#ff2244" />
      <Metric label="Analysts"     value={metrics.ws_connections ?? 1} color="#a78bfa" />

      <div style={{ flex: 1 }} />

      <div style={{ padding: "0 20px", fontSize: "11px", color: "#334155" }}>
        {new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
      </div>
    </div>
  );
}
