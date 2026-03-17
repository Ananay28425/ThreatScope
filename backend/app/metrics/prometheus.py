"""
Custom Prometheus metrics for ThreatScope.

These metrics are what you'll showcase in Grafana during your stress test demo.
Each metric answers a specific operational question:

  signals_ingested_total  → How many privacy-safe signals has the system processed?
  alerts_raised_total     → How frequently are cross-node attacks being detected?
  correlation_latency     → Is the engine keeping up under load?
  active_nodes            → How many orgs are live right now?
  websocket_connections   → How many analysts are on the SOC dashboard?
"""

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

# ── Ingestion ────────────────────────────────────────────────────────────────

signals_ingested_total = Counter(
    "threatscope_signals_ingested_total",
    "Total signals received from all nodes",
    labelnames=["node_id", "fingerprint"],
)

# ── Alerting ─────────────────────────────────────────────────────────────────

alerts_raised_total = Counter(
    "threatscope_alerts_raised_total",
    "Global alerts raised by the correlation engine",
    labelnames=["severity", "fingerprint"],
)

# ── Correlation Engine Performance ────────────────────────────────────────────

correlation_latency_seconds = Histogram(
    "threatscope_correlation_latency_seconds",
    "Time taken by the correlation engine to evaluate one signal batch",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# ── System Health ─────────────────────────────────────────────────────────────

active_nodes = Gauge(
    "threatscope_active_nodes",
    "Number of currently active organization nodes",
)

websocket_connections = Gauge(
    "threatscope_websocket_connections_active",
    "Number of open WebSocket connections to the SOC dashboard",
)

valkey_stream_lag = Gauge(
    "threatscope_valkey_stream_lag_messages",
    "Number of unprocessed messages in the Valkey signal stream",
)
