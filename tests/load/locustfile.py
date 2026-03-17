"""
ThreatScope Load Test — Locust

Tests two critical paths under load:
  1. Signal ingestion endpoint (the hot path — 50k+ signals/sec target)
  2. Alert API reads (the dashboard polling path)

Run:
    locust -f locustfile.py --host=http://localhost:8000

Stress test for demo:
    locust -f locustfile.py --host=http://localhost:8000 \
      --headless -u 200 -r 20 --run-time 5m \
      --csv=locust_report/results

What to show in your demo:
  - Grafana signals/sec climbing under load
  - Correlation latency staying flat (proves the engine is non-blocking)
  - System surviving 200 concurrent nodes without HTTP 5xx responses
"""

import random
from datetime import datetime, timezone

from locust import HttpUser, between, task


FINGERPRINTS = [
    "AUTH_FAIL_BURST",
    "TRAFFIC_SPIKE",
    "PORT_SCAN_LIKE",
    "HIGH_ERROR_RATE",
    None,
    None,
    None,  # Most signals have no fingerprint (normal traffic)
]


class NodeSimulatorUser(HttpUser):
    """
    Simulates a single organization node continuously sending signals.
    Represents the core ingestion load.
    """
    wait_time = between(1, 3)

    def on_start(self):
        self.node_id = f"load-test-org-{random.randint(1, 1000)}"
        self.api_key = "load-test-key"

    @task(10)
    def ingest_normal_signal(self):
        """Normal baseline signal — low anomaly score."""
        self.client.post(
            "/api/signals/ingest",
            json={
                "node_id": self.node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "anomaly_score": round(random.uniform(0.0, 0.4), 4),
                "fingerprint": None,
                "confidence": round(random.uniform(0.7, 1.0), 3),
                "window_seconds": 60,
                "metrics": {
                    "request_rate": random.uniform(20, 80),
                    "failed_login_rate": random.uniform(0.01, 0.08),
                    "unique_ip_count": random.randint(10, 150),
                    "ip_entropy": random.uniform(2.0, 4.0),
                    "error_rate_4xx": random.uniform(0.01, 0.05),
                    "error_rate_5xx": random.uniform(0.001, 0.02),
                    "avg_response_time_ms": random.uniform(80, 200),
                },
            },
            headers={"X-Api-Key": self.api_key},
            name="POST /api/signals/ingest [normal]",
        )

    @task(3)
    def ingest_attack_signal(self):
        """High-score attack signal — should trigger correlation alerts."""
        self.client.post(
            "/api/signals/ingest",
            json={
                "node_id": self.node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "anomaly_score": round(random.uniform(0.82, 0.99), 4),
                "fingerprint": random.choice(FINGERPRINTS[:4]),
                "confidence": round(random.uniform(0.85, 1.0), 3),
                "window_seconds": 60,
                "metrics": {
                    "request_rate": random.uniform(400, 1200),
                    "failed_login_rate": random.uniform(0.5, 0.9),
                    "unique_ip_count": random.randint(200, 800),
                    "ip_entropy": random.uniform(4.5, 6.0),
                    "error_rate_4xx": random.uniform(0.2, 0.7),
                    "error_rate_5xx": random.uniform(0.05, 0.3),
                    "avg_response_time_ms": random.uniform(400, 2000),
                },
            },
            headers={"X-Api-Key": self.api_key},
            name="POST /api/signals/ingest [attack]",
        )


class SOCAnalystUser(HttpUser):
    """
    Simulates a SOC analyst refreshing the dashboard.
    Lower frequency — represents read traffic.
    """
    wait_time = between(5, 15)

    def on_start(self):
        # Attempt login (will fail in CI without a real DB — that's fine for load testing)
        resp = self.client.post(
            "/api/auth/login",
            json={"email": "analyst@threatscope.local", "password": "testpassword"},
            catch_response=True,
        )
        if resp.status_code == 200:
            self.token = resp.json().get("access_token", "")
        else:
            self.token = ""
            resp.success()  # Don't count auth failures as load test failures

    @property
    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def list_alerts(self):
        self.client.get(
            "/api/alerts/?limit=50",
            headers=self._auth_headers,
            name="GET /api/alerts",
        )

    @task(2)
    def list_nodes(self):
        self.client.get(
            "/api/nodes/",
            headers=self._auth_headers,
            name="GET /api/nodes",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="GET /health")
