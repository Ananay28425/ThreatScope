import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect } from "react";
import { useWebSocket } from "../hooks/useWebSocket.js";
import { useThreatStore } from "../store/threatStore.js";
import { useAuthStore } from "../store/authStore.js";

const shellStyles = {
  root: {
    minHeight: "100vh",
    display: "grid",
    gridTemplateColumns: "260px 1fr",
    background:
      "radial-gradient(circle at top, rgba(15,23,42,0.96) 0%, rgba(2,6,23,1) 60%)",
    color: "#e2e8f0",
    fontFamily:
      'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  sidebar: {
    borderRight: "1px solid rgba(51, 65, 85, 0.55)",
    background: "rgba(2, 6, 23, 0.92)",
    backdropFilter: "blur(10px)",
    display: "flex",
    flexDirection: "column",
    padding: "20px 16px",
    gap: "20px",
  },
  brandWrap: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    paddingBottom: "16px",
    borderBottom: "1px solid rgba(51, 65, 85, 0.55)",
  },
  brandTitle: {
    margin: 0,
    fontSize: "22px",
    fontWeight: 800,
    letterSpacing: "0.04em",
    color: "#f8fafc",
  },
  brandTag: {
    margin: 0,
    fontSize: "12px",
    color: "#93c5fd",
    letterSpacing: "0.16em",
    textTransform: "uppercase",
  },
  sectionLabel: {
    fontSize: "11px",
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.14em",
    marginBottom: "10px",
    fontWeight: 700,
  },
  nav: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  navLink: {
    textDecoration: "none",
    color: "#cbd5e1",
    padding: "12px 14px",
    borderRadius: "12px",
    border: "1px solid transparent",
    transition: "all 0.2s ease",
    fontSize: "14px",
    fontWeight: 600,
  },
  statusCard: {
    marginTop: "auto",
    background: "rgba(15, 23, 42, 0.78)",
    border: "1px solid rgba(51, 65, 85, 0.55)",
    borderRadius: "14px",
    padding: "14px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  main: {
    minWidth: 0,
    display: "flex",
    flexDirection: "column",
  },
  topbar: {
    height: "72px",
    borderBottom: "1px solid rgba(51, 65, 85, 0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 24px",
    background: "rgba(2, 6, 23, 0.45)",
    backdropFilter: "blur(8px)",
    position: "sticky",
    top: 0,
    zIndex: 10,
  },
  pageTitle: {
    margin: 0,
    fontSize: "18px",
    fontWeight: 700,
    color: "#f8fafc",
  },
  pageSubtitle: {
    margin: "4px 0 0",
    fontSize: "12px",
    color: "#94a3b8",
  },
  topbarRight: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
  },
  badge: {
    display: "inline-flex",
    alignItems: "center",
    gap: "8px",
    borderRadius: "999px",
    padding: "8px 12px",
    fontSize: "12px",
    fontWeight: 700,
    border: "1px solid rgba(71, 85, 105, 0.6)",
    background: "rgba(15, 23, 42, 0.7)",
    color: "#cbd5e1",
  },
  content: {
    flex: 1,
    minHeight: 0,
    padding: "20px",
  },
  userBox: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 12px",
    borderRadius: "12px",
    background: "rgba(15, 23, 42, 0.7)",
    border: "1px solid rgba(51, 65, 85, 0.55)",
  },
  avatar: {
    width: "34px",
    height: "34px",
    borderRadius: "50%",
    display: "grid",
    placeItems: "center",
    background: "linear-gradient(135deg, #2563eb 0%, #38bdf8 100%)",
    color: "#fff",
    fontWeight: 800,
    fontSize: "13px",
  },
  userMeta: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  userName: {
    fontSize: "13px",
    fontWeight: 700,
    color: "#f8fafc",
    lineHeight: 1.2,
  },
  userRole: {
    fontSize: "11px",
    color: "#94a3b8",
    lineHeight: 1.2,
  },
  logoutButton: {
    border: "1px solid rgba(239, 68, 68, 0.35)",
    background: "rgba(127, 29, 29, 0.25)",
    color: "#fecaca",
    borderRadius: "10px",
    padding: "10px 12px",
    fontSize: "12px",
    fontWeight: 700,
    cursor: "pointer",
  },
};

function getPageMeta(pathname) {
  if (pathname === "/alerts") {
    return {
      title: "Alerts",
      subtitle: "Investigate correlated incidents and distributed attack signals.",
    };
  }

  if (pathname === "/threat-map") {
    return {
      title: "Threat Map",
      subtitle: "Visualize node activity and high-confidence threat correlations.",
    };
  }

  return {
    title: "Dashboard",
    subtitle: "Monitor live signals, alerts, node health, and system telemetry.",
  };
}

function getNavLinkStyle({ isActive }) {
  return {
    ...shellStyles.navLink,
    background: isActive ? "rgba(37, 99, 235, 0.16)" : "transparent",
    borderColor: isActive ? "rgba(59, 130, 246, 0.45)" : "transparent",
    color: isActive ? "#dbeafe" : "#cbd5e1",
    boxShadow: isActive ? "0 0 0 1px rgba(59, 130, 246, 0.08) inset" : "none",
  };
}

function StatusDot({ connected }) {
  return (
    <span
      style={{
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: connected ? "#22c55e" : "#ef4444",
        boxShadow: connected
          ? "0 0 10px rgba(34, 197, 94, 0.8)"
          : "0 0 10px rgba(239, 68, 68, 0.8)",
        display: "inline-block",
      }}
    />
  );
}

export default function AppShell() {
  useWebSocket();

  const location = useLocation();
  const wsConnected = useThreatStore((state) => state.wsConnected);
  const alerts = useThreatStore((state) => state.alerts);
  const nodes = useThreatStore((state) => state.nodes);
  const metrics = useThreatStore((state) => state.metrics);

  const user = useAuthStore((state) => state.user);
  const clearAuth = useAuthStore((state) => state.clearAuth);
  const token = useAuthStore((state) => state.token);

  useEffect(() => {
    if (!token) {
      return;
    }
  }, [token]);

  const page = getPageMeta(location.pathname);
  const nodeCount = Object.keys(nodes || {}).length;
  const openAlerts = alerts.filter((alert) => alert.status !== "resolved").length;
  const displayName =
    user?.name || user?.email || user?.username || "SOC Analyst";
  const initials = displayName
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("") || "TS";

  const handleLogout = () => {
    clearAuth?.();
  };

  return (
    <div style={shellStyles.root}>
      <aside style={shellStyles.sidebar}>
        <div style={shellStyles.brandWrap}>
          <p style={shellStyles.brandTag}>ThreatScope</p>
          <h1 style={shellStyles.brandTitle}>SOC Console</h1>
          <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8", lineHeight: 1.6 }}>
            Privacy-preserving cyber threat intelligence and distributed alerting.
          </p>
        </div>

        <div>
          <div style={shellStyles.sectionLabel}>Navigation</div>
          <nav style={shellStyles.nav}>
            <NavLink to="/" end style={getNavLinkStyle}>
              Overview Dashboard
            </NavLink>
            <NavLink to="/alerts" style={getNavLinkStyle}>
              Alerts Panel
            </NavLink>
            <NavLink to="/threat-map" style={getNavLinkStyle}>
              Threat Map
            </NavLink>
          </nav>
        </div>

        <div style={shellStyles.statusCard}>
          <div style={shellStyles.sectionLabel}>System Status</div>

          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
            <span style={{ color: "#94a3b8", fontSize: "13px" }}>WebSocket</span>
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                color: wsConnected ? "#bbf7d0" : "#fecaca",
                fontSize: "12px",
                fontWeight: 700,
              }}
            >
              <StatusDot connected={wsConnected} />
              {wsConnected ? "Connected" : "Disconnected"}
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
            <span style={{ color: "#94a3b8", fontSize: "13px" }}>Open Alerts</span>
            <span style={{ color: "#f8fafc", fontSize: "13px", fontWeight: 700 }}>
              {openAlerts}
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
            <span style={{ color: "#94a3b8", fontSize: "13px" }}>Tracked Nodes</span>
            <span style={{ color: "#f8fafc", fontSize: "13px", fontWeight: 700 }}>
              {nodeCount}
            </span>
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", gap: "12px" }}>
            <span style={{ color: "#94a3b8", fontSize: "13px" }}>Signals / sec</span>
            <span style={{ color: "#f8fafc", fontSize: "13px", fontWeight: 700 }}>
              {metrics?.signals_per_sec ?? 0}
            </span>
          </div>
        </div>
      </aside>

      <main style={shellStyles.main}>
        <header style={shellStyles.topbar}>
          <div>
            <h2 style={shellStyles.pageTitle}>{page.title}</h2>
            <p style={shellStyles.pageSubtitle}>{page.subtitle}</p>
          </div>

          <div style={shellStyles.topbarRight}>
            <div style={shellStyles.badge}>
              <StatusDot connected={wsConnected} />
              {wsConnected ? "Live feed active" : "Live feed offline"}
            </div>

            <div style={shellStyles.badge}>
              Active Nodes: {metrics?.active_nodes ?? nodeCount}
            </div>

            <div style={shellStyles.userBox}>
              <div style={shellStyles.avatar}>{initials}</div>
              <div style={shellStyles.userMeta}>
                <span style={shellStyles.userName}>{displayName}</span>
                <span style={shellStyles.userRole}>
                  {user?.role || "security-analyst"}
                </span>
              </div>
            </div>

            <button type="button" onClick={handleLogout} style={shellStyles.logoutButton}>
              Logout
            </button>
          </div>
        </header>

        <section style={shellStyles.content}>
          <Outlet />
        </section>
      </main>
    </div>
  );
}
