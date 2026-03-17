import { useEffect, useMemo, useRef, useState } from "react";
import { useThreatStore } from "../store/threatStore.js";

const CANVAS_WIDTH = 900;
const CANVAS_HEIGHT = 420;
const PULSE_LIFETIME_MS = 3200;

const NODE_POSITIONS = {
  org_1: { x: 170, y: 120, region: "North America" },
  org_2: { x: 290, y: 110, region: "South America" },
  org_3: { x: 470, y: 100, region: "Europe" },
  org_4: { x: 560, y: 145, region: "Africa" },
  org_5: { x: 690, y: 135, region: "Asia" },
  org_6: { x: 765, y: 220, region: "Oceania" },
  org_7: { x: 455, y: 220, region: "Mediterranean" },
  org_8: { x: 620, y: 230, region: "South Asia" },
  org_9: { x: 120, y: 235, region: "Pacific" },
  org_10: { x: 360, y: 255, region: "Atlantic" },
};

const SEVERITY_COLORS = {
  CRITICAL: "#ff3355",
  HIGH: "#ff7a18",
  MEDIUM: "#ffc247",
  LOW: "#3cb6ff",
};

const DEFAULT_COLOR = "#58a6ff";

function hashString(input = "") {
  let hash = 0;
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

function fallbackPosition(nodeId, index) {
  const seed = hashString(nodeId || String(index));
  const x = 90 + (seed % 700);
  const y = 80 + ((seed >> 3) % 240);
  return { x, y, region: "Distributed Node" };
}

function getNodePosition(nodeId, index = 0) {
  return NODE_POSITIONS[nodeId] || fallbackPosition(nodeId, index);
}

function formatRelativeTime(isoString) {
  if (!isoString) return "never";
  const ts = new Date(isoString).getTime();
  if (Number.isNaN(ts)) return "unknown";

  const deltaMs = Date.now() - ts;
  const seconds = Math.floor(deltaMs / 1000);

  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function isNodeHot(node) {
  return (node?.anomaly_score ?? 0) >= 0.8;
}

function nodeStatusColor(node) {
  if (!node?.is_active) return "#334155";
  if ((node?.anomaly_score ?? 0) >= 0.9) return SEVERITY_COLORS.HIGH;
  if ((node?.anomaly_score ?? 0) >= 0.8) return SEVERITY_COLORS.MEDIUM;
  return "#22c55e";
}

function buildCurvedPath(from, to) {
  const mx = (from.x + to.x) / 2;
  const my = (from.y + to.y) / 2 - 40;
  return `M ${from.x} ${from.y} Q ${mx} ${my} ${to.x} ${to.y}`;
}

function buildPulseList(nodes, alerts) {
  const now = Date.now();

  const nodePulses = Object.entries(nodes)
    .filter(([, node]) => node?.last_seen)
    .map(([nodeId, node], index) => ({
      id: `node-${nodeId}`,
      nodeId,
      x: getNodePosition(nodeId, index).x,
      y: getNodePosition(nodeId, index).y,
      startedAt: new Date(node.last_seen).getTime(),
      severity:
        (node?.anomaly_score ?? 0) >= 0.95
          ? "CRITICAL"
          : (node?.anomaly_score ?? 0) >= 0.9
            ? "HIGH"
            : (node?.anomaly_score ?? 0) >= 0.8
              ? "MEDIUM"
              : "LOW",
      fingerprint: node?.fingerprint || null,
    }))
    .filter((pulse) => now - pulse.startedAt <= PULSE_LIFETIME_MS);

  const alertPulses = alerts
    .slice(0, 12)
    .flatMap((alert) =>
      (alert.contributing_nodes || []).map((nodeId, index) => ({
        id: `alert-${alert.id}-${nodeId}-${index}`,
        nodeId,
        x: getNodePosition(nodeId, index).x,
        y: getNodePosition(nodeId, index).y,
        startedAt: new Date(alert.received_at || Date.now()).getTime(),
        severity: alert.severity || "LOW",
        fingerprint: alert.fingerprint || null,
      })),
    )
    .filter((pulse) => now - pulse.startedAt <= PULSE_LIFETIME_MS);

  const deduped = new Map();
  [...nodePulses, ...alertPulses].forEach((pulse) => {
    const existing = deduped.get(pulse.id);
    if (!existing || existing.startedAt < pulse.startedAt) {
      deduped.set(pulse.id, pulse);
    }
  });

  return [...deduped.values()];
}

export default function ThreatMap() {
  const nodes = useThreatStore((s) => s.nodes);
  const alerts = useThreatStore((s) => s.alerts);
  const wsConnected = useThreatStore((s) => s.wsConnected);

  const tickRef = useRef(0);
  const [, forceTick] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      tickRef.current += 1;
      forceTick((n) => n + 1);
    }, 500);

    return () => clearInterval(interval);
  }, [forceTick]);

  const nodeEntries = useMemo(() => {
    return Object.entries(nodes).map(([nodeId, node], index) => {
      const position = getNodePosition(nodeId, index);
      return {
        nodeId,
        node,
        ...position,
      };
    });
  }, [nodes]);

  const activeHotNodes = useMemo(() => {
    return nodeEntries.filter(
      (entry) => entry.node?.is_active && isNodeHot(entry.node),
    );
  }, [nodeEntries]);

  const links = useMemo(() => {
    if (activeHotNodes.length < 2) return [];
    const anchor = activeHotNodes[0];

    return activeHotNodes.slice(1).map((target) => ({
      id: `${anchor.nodeId}-${target.nodeId}`,
      from: anchor,
      to: target,
    }));
  }, [activeHotNodes]);

  const pulses = useMemo(
    () => buildPulseList(nodes, alerts),
    [nodes, alerts, tickRef.current],
  );

  const latestAlert = alerts[0] || null;

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: 360,
        background:
          "radial-gradient(circle at 50% 45%, rgba(15,23,42,0.95) 0%, rgba(2,6,23,1) 70%)",
        borderRadius: 12,
        overflow: "hidden",
        border: "1px solid rgba(37, 99, 235, 0.18)",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            "linear-gradient(rgba(59,130,246,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.08) 1px, transparent 1px)",
          backgroundSize: "36px 36px",
          opacity: 0.35,
          pointerEvents: "none",
        }}
      />

      <div
        style={{
          position: "absolute",
          top: 14,
          left: 16,
          zIndex: 2,
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <div
          style={{
            fontSize: 12,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "#93c5fd",
            fontWeight: 700,
          }}
        >
          Threat Map
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8" }}>
          {wsConnected ? "Live stream connected" : "Stream disconnected"}
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          top: 14,
          right: 16,
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          gap: 10,
          fontSize: 12,
          color: "#cbd5e1",
          background: "rgba(15, 23, 42, 0.72)",
          border: "1px solid rgba(71, 85, 105, 0.5)",
          borderRadius: 10,
          padding: "8px 10px",
          backdropFilter: "blur(6px)",
        }}
      >
        <LegendDot color="#22c55e" label="Active" />
        <LegendDot color={SEVERITY_COLORS.MEDIUM} label="Elevated" />
        <LegendDot color={SEVERITY_COLORS.HIGH} label="High risk" />
        <LegendDot color={SEVERITY_COLORS.CRITICAL} label="Critical" />
      </div>

      <svg
        viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
        style={{ width: "100%", height: "100%", display: "block" }}
        role="img"
        aria-label="ThreatScope threat activity map"
      >
        <defs>
          <radialGradient id="glowBlue" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="rgba(96,165,250,0.55)" />
            <stop offset="100%" stopColor="rgba(96,165,250,0)" />
          </radialGradient>

          <filter id="softGlow">
            <feGaussianBlur stdDeviation="4" result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <ellipse
          cx="450"
          cy="210"
          rx="310"
          ry="118"
          fill="url(#glowBlue)"
          opacity="0.45"
        />

        <path
          d="M145 160 C220 120, 300 110, 360 135 C430 165, 520 145, 615 120 C690 100, 760 125, 790 165"
          fill="none"
          stroke="rgba(96,165,250,0.18)"
          strokeWidth="36"
          strokeLinecap="round"
        />
        <path
          d="M135 230 C205 200, 280 195, 360 210 C455 230, 550 220, 640 205 C710 192, 760 208, 790 235"
          fill="none"
          stroke="rgba(56,189,248,0.12)"
          strokeWidth="28"
          strokeLinecap="round"
        />

        {links.map((link) => (
          <g key={link.id}>
            <path
              d={buildCurvedPath(link.from, link.to)}
              fill="none"
              stroke="rgba(250, 204, 21, 0.22)"
              strokeWidth="2"
              strokeDasharray="7 9"
            />
            <path
              d={buildCurvedPath(link.from, link.to)}
              fill="none"
              stroke="rgba(248, 113, 113, 0.35)"
              strokeWidth="4"
              strokeLinecap="round"
              opacity="0.25"
            />
          </g>
        ))}

        {pulses.map((pulse) => {
          const age = Date.now() - pulse.startedAt;
          const progress = Math.min(age / PULSE_LIFETIME_MS, 1);
          const radius = 12 + progress * 44;
          const opacity = 0.9 - progress * 0.9;
          const color = SEVERITY_COLORS[pulse.severity] || DEFAULT_COLOR;

          return (
            <g key={pulse.id} pointerEvents="none">
              <circle
                cx={pulse.x}
                cy={pulse.y}
                r={radius}
                fill="none"
                stroke={color}
                strokeWidth="2.4"
                opacity={opacity}
              />
              <circle
                cx={pulse.x}
                cy={pulse.y}
                r={Math.max(4, radius * 0.45)}
                fill={color}
                opacity={opacity * 0.18}
              />
            </g>
          );
        })}

        {nodeEntries.map(({ nodeId, node, x, y, region }) => {
          const color = nodeStatusColor(node);
          const active = Boolean(node?.is_active);
          const score = node?.anomaly_score ?? 0;

          return (
            <g key={nodeId} filter={active ? "url(#softGlow)" : undefined}>
              <circle
                cx={x}
                cy={y}
                r={active ? 13 : 9}
                fill={active ? "rgba(15,23,42,0.95)" : "rgba(30,41,59,0.85)"}
                stroke={color}
                strokeWidth={active ? 2.5 : 1.5}
              />
              <circle
                cx={x}
                cy={y}
                r={active ? 5 : 3}
                fill={color}
                opacity={active ? 1 : 0.7}
              />

              <text
                x={x}
                y={y + 27}
                textAnchor="middle"
                fill="#e2e8f0"
                fontSize="11"
                fontWeight="600"
              >
                {nodeId}
              </text>
              <text
                x={x}
                y={y + 42}
                textAnchor="middle"
                fill="#64748b"
                fontSize="9"
              >
                {region}
              </text>

              {active && (
                <text
                  x={x}
                  y={y - 18}
                  textAnchor="middle"
                  fill={color}
                  fontSize="9"
                  fontWeight="700"
                >
                  {(score ?? 0).toFixed(2)}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <div
        style={{
          position: "absolute",
          left: 16,
          bottom: 16,
          zIndex: 2,
          display: "grid",
          gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
          gap: 10,
          width: "min(520px, calc(100% - 32px))",
        }}
      >
        <MetricCard
          label="Tracked nodes"
          value={String(nodeEntries.length)}
          tone="#93c5fd"
        />
        <MetricCard
          label="Active hot nodes"
          value={String(activeHotNodes.length)}
          tone={activeHotNodes.length > 0 ? "#fbbf24" : "#22c55e"}
        />
        <MetricCard
          label="Latest alert"
          value={latestAlert ? latestAlert.severity : "None"}
          tone={
            latestAlert
              ? SEVERITY_COLORS[latestAlert.severity] || DEFAULT_COLOR
              : "#94a3b8"
          }
        />
      </div>

      <div
        style={{
          position: "absolute",
          right: 16,
          bottom: 16,
          zIndex: 2,
          width: 260,
          maxWidth: "calc(100% - 32px)",
          background: "rgba(2, 6, 23, 0.8)",
          border: "1px solid rgba(71, 85, 105, 0.45)",
          borderRadius: 12,
          padding: 12,
          backdropFilter: "blur(10px)",
          color: "#e2e8f0",
        }}
      >
        <div
          style={{
            fontSize: 11,
            textTransform: "uppercase",
            letterSpacing: "0.12em",
            color: "#94a3b8",
            marginBottom: 8,
          }}
        >
          Latest Activity
        </div>

        {latestAlert ? (
          <>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                color: SEVERITY_COLORS[latestAlert.severity] || DEFAULT_COLOR,
                marginBottom: 6,
              }}
            >
              {latestAlert.fingerprint
                ? latestAlert.fingerprint.replace(/_/g, " ")
                : "Correlated anomaly"}
            </div>
            <div style={{ fontSize: 12, color: "#cbd5e1", marginBottom: 6 }}>
              Severity: {latestAlert.severity}
            </div>
            <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
              Nodes:{" "}
              {(latestAlert.contributing_nodes || []).join(", ") || "n/a"}
            </div>
            <div style={{ fontSize: 11, color: "#64748b" }}>
              Received {formatRelativeTime(latestAlert.received_at)}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 12, color: "#94a3b8" }}>
            No correlated alerts yet. The map will highlight activity as signals
            arrive.
          </div>
        )}
      </div>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          width: 9,
          height: 9,
          borderRadius: "999px",
          background: color,
          boxShadow: `0 0 10px ${color}`,
          display: "inline-block",
        }}
      />
      <span>{label}</span>
    </div>
  );
}

function MetricCard({ label, value, tone }) {
  return (
    <div
      style={{
        background: "rgba(15, 23, 42, 0.75)",
        border: "1px solid rgba(71, 85, 105, 0.4)",
        borderRadius: 10,
        padding: "10px 12px",
        backdropFilter: "blur(8px)",
      }}
    >
      <div
        style={{
          fontSize: 10,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: "#64748b",
          marginBottom: 6,
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: 18, fontWeight: 700, color: tone }}>{value}</div>
    </div>
  );
}
