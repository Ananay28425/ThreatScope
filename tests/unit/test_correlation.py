"""
Unit tests for the ThreatScope correlation engine.

Tests verify that:
  - Alerts fire only when threshold conditions are met
  - Alerts do NOT fire on insufficient nodes or low scores
  - Severity classification is correct
  - Pruning correctly removes stale records

Run: pytest tests/unit/test_correlation.py -v
"""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.correlation.engine import CorrelationEngine, SignalRecord
from app.core.config import settings


def _record(
    node_id: str,
    score: float,
    fingerprint: str = "AUTH_FAIL_BURST",
    seconds_ago: float = 0,
    confidence: float = 1.0,
) -> SignalRecord:
    ts = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return SignalRecord(
        node_id=node_id,
        timestamp=ts,
        anomaly_score=score,
        fingerprint=fingerprint,
        confidence=confidence,
    )


@pytest.fixture
def engine() -> CorrelationEngine:
    e = CorrelationEngine()
    e.broadcast = None  # disable WS broadcast in tests
    return e


class TestCorrelationEngine:
    def test_no_alert_below_node_threshold(self, engine):
        """Alert should NOT fire with only 2 nodes (threshold = 3)."""
        alerts = []

        async def fake_broadcast(data):
            alerts.append(data)

        engine.broadcast = fake_broadcast

        asyncio.run(engine.ingest(_record("org_1", 0.95)))
        asyncio.run(engine.ingest(_record("org_2", 0.90)))

        assert len(alerts) == 0, "Alert fired with only 2 nodes — threshold not enforced"

    def test_alert_fires_at_threshold(self, engine):
        """Alert MUST fire when exactly N=3 nodes report high scores."""
        alerts = []

        async def fake_broadcast(data):
            alerts.append(data)

        engine.broadcast = fake_broadcast

        asyncio.run(engine.ingest(_record("org_1", 0.92)))
        asyncio.run(engine.ingest(_record("org_2", 0.88)))
        asyncio.run(engine.ingest(_record("org_3", 0.85)))

        assert len(alerts) == 1, f"Expected 1 alert, got {len(alerts)}"
        assert alerts[0]["event_type"] == "new_alert"

    def test_no_alert_when_score_below_threshold(self, engine):
        """Nodes below the score threshold should not trigger correlation."""
        alerts = []

        async def fake_broadcast(data):
            alerts.append(data)

        engine.broadcast = fake_broadcast

        # Scores below 0.80 should be ignored even with 5 nodes
        for i in range(5):
            asyncio.run(engine.ingest(_record(f"org_{i}", 0.60)))

        assert len(alerts) == 0

    def test_duplicate_node_does_not_double_count(self, engine):
        """Same node sending multiple signals should count as one node."""
        alerts = []

        async def fake_broadcast(data):
            alerts.append(data)

        engine.broadcast = fake_broadcast

        # Org 1 sends 5 signals — still counts as 1 node
        for _ in range(5):
            asyncio.run(engine.ingest(_record("org_1", 0.95)))

        asyncio.run(engine.ingest(_record("org_2", 0.90)))
        # Only 2 distinct nodes — alert should NOT fire

        assert len(alerts) == 0

    def test_severity_classification_critical(self, engine):
        assert engine._classify_severity(0.97, 10) == "CRITICAL"

    def test_severity_classification_high(self, engine):
        assert engine._classify_severity(0.91, 4) == "HIGH"

    def test_severity_classification_medium(self, engine):
        assert engine._classify_severity(0.82, 3) == "MEDIUM"

    def test_stale_records_are_pruned(self, engine):
        """Records outside the correlation window should be removed."""
        key = "AUTH_FAIL_BURST"
        # Add records that are already outside the window
        old = _record("org_1", 0.95, seconds_ago=settings.correlation_window_seconds + 10)
        engine._buffer[key].append(old)

        engine._prune(key)

        assert len(engine._buffer[key]) == 0, "Stale record was not pruned"
