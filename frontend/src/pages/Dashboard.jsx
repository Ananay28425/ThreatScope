/**
 * Dashboard — the main SOC command center layout.
 *
 * Layout:
 *   ┌────────────────── MetricsBar ──────────────────────┐
 *   │ NodeStatus │     ThreatGlobe (3D)     │ AlertFeed  │
 *   └────────────────────────────────────────────────────┘
 *
 * All data flows in via the useWebSocket hook → Zustand store → components.
 * No component polls the REST API for live data.
 */

import { Suspense } from "react";
import MetricsBar from "../components/MetricsBar.jsx";
import AlertFeed from "../components/AlertFeed.jsx";
import NodeStatus from "../components/NodeStatus.jsx";
import ThreatGlobe from "../three/ThreatGlobe.jsx";
import { useWebSocket } from "../hooks/useWebSocket.js";

const PANEL_STYLE = {
  background: "#070d16",
  border: "1px solid #0f2035",
  borderRadius: "8px",
  padding: "12px 16px",
  overflow: "hidden",
};

export default function Dashboard() {
  // Connect to the SOC stream — this hook runs once for the lifetime of the page
  useWebSocket();

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#050a10" }}>
      {/* Top bar */}
      <MetricsBar />

      {/* Main 3-column layout */}
      <div style={{
        flex: 1,
        display: "grid",
        gridTemplateColumns: "260px 1fr 320px",
        gap: "10px",
        padding: "10px",
        overflow: "hidden",
      }}>
        {/* Left: Node Status */}
        <div style={PANEL_STYLE}>
          <NodeStatus />
        </div>

        {/* Centre: 3D Threat Globe */}
        <div style={{ ...PANEL_STYLE, padding: 0, position: "relative" }}>
          <Suspense fallback={
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#334155", fontSize: "13px" }}>
              Initialising threat globe…
            </div>
          }>
            <ThreatGlobe />
          </Suspense>

          {/* Overlay label */}
          <div style={{
            position: "absolute",
            bottom: 14,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: "10px",
            color: "#334155",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            pointerEvents: "none",
          }}>
            Global Threat Map · Drag to rotate
          </div>
        </div>

        {/* Right: Alert Feed */}
        <div style={PANEL_STYLE}>
          <AlertFeed />
        </div>
      </div>
    </div>
  );
}
