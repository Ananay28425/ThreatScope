import AlertFeed from "./AlertFeed.jsx";
import MetricsBar from "./MetricsBar.jsx";
import NodeStatus from "./NodeStatus.jsx";
import ThreatMap from "./ThreatMap.jsx";

const panelStyle = {
  background: "#070d16",
  border: "1px solid #0f2035",
  borderRadius: "8px",
  padding: "12px 16px",
  overflow: "hidden",
};

export default function Dashboard() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        minHeight: "100vh",
        background: "#050a10",
        color: "#e2e8f0",
      }}
    >
      <MetricsBar />

      <div
        style={{
          flex: 1,
          display: "grid",
          gridTemplateColumns: "260px 1fr 320px",
          gap: "10px",
          padding: "10px",
          overflow: "hidden",
        }}
      >
        <div style={panelStyle}>
          <NodeStatus />
        </div>

        <div style={{ ...panelStyle, padding: 0, position: "relative" }}>
          <ThreatMap />
          <div
            style={{
              position: "absolute",
              bottom: 14,
              left: "50%",
              transform: "translateX(-50%)",
              fontSize: "10px",
              color: "#334155",
              letterSpacing: "0.15em",
              textTransform: "uppercase",
              pointerEvents: "none",
            }}
          >
            Global Threat Map · Live View
          </div>
        </div>

        <div style={panelStyle}>
          <AlertFeed />
        </div>
      </div>
    </div>
  );
}
