import { Routes, Route, Navigate } from "react-router-dom";
import AppShell from "./components/AppShell.jsx";
import Dashboard from "./components/Dashboard.jsx";
import AlertsPanel from "./components/AlertsPanel.jsx";
import ThreatMap from "./components/ThreatMap.jsx";
import Login from "./pages/Login.jsx";
import { useAuthStore } from "./store/authStore.js";

function ProtectedRoute({ children }) {
  const token = useAuthStore((state) => state.token);
  return token ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const token = useAuthStore((state) => state.token);

  return (
    <Routes>
      <Route
        path="/login"
        element={token ? <Navigate to="/" replace /> : <Login />}
      />

      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="alerts" element={<AlertsPanel />} />
        <Route path="threat-map" element={<ThreatMap />} />
      </Route>

      <Route
        path="*"
        element={<Navigate to={token ? "/" : "/login"} replace />}
      />
    </Routes>
  );
}
