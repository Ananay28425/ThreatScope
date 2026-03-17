"""
Compatibility tests for the ThreatScope correlator service and core correlation engine.

These tests are intentionally lightweight and filesystem-independent so they can
run even while the repository is still being restructured.

Coverage goals:
- Verify the core engine still raises alerts at the configured threshold
- Verify stale records are pruned
- Verify the service wrapper returns structured correlation results
- Verify generated alert payloads match the documented contract shape
"""

from datetime import datetime, timedelta, timezone

import pytest
from app.core.config import settings
from app.correlation.engine import CorrelationEngine, SignalRecord
from app.services.correlator import CorrelatorService


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
    instance = CorrelationEngine()
    instance.broadcast = None
    return instance


@pytest.fixture
def correlator(engine: CorrelationEngine) -> CorrelatorService:
    return CorrelatorService(engine=engine)


class TestCorrelationEngineCompatibility:
    @pytest.mark.asyncio
    async def test_alert_fires_when_distinct_nodes_meet_threshold(self, engine: CorrelationEngine):
        alerts = []

        async def fake_broadcast(payload):
            alerts.append(payload)

        engine.broadcast = fake_broadcast

        await engine.ingest(_record("org_1", 0.92))
        await engine.ingest(_record("org_2", 0.88))
        await engine.ingest(_record("org_3", 0.86))

        assert len(alerts) == 1
        assert alerts[0]["event_type"] == "new_alert"
        assert alerts[0]["payload"]["fingerprint"] == "AUTH_FAIL_BURST"
        assert alerts[0]["payload"]["node_count"] == 3

    @pytest.mark.asyncio
    async def test_duplicate_node_does_not_double_count(self, engine: CorrelationEngine):
        alerts = []

        async def fake_broadcast(payload):
            alerts.append(payload)

        engine.broadcast = fake_broadcast

        await engine.ingest(_record("org_1", 0.95))
        await engine.ingest(_record("org_1", 0.97))
        await engine.ingest(_record("org_2", 0.91))

        assert alerts == []

    def test_prune_removes_stale_records(self, engine: CorrelationEngine):
        key = "AUTH_FAIL_BURST"
        stale = _record(
            "org_old",
            0.95,
            fingerprint=key,
            seconds_ago=settings.correlation_window_seconds + 5,
        )
        fresh = _record("org_new", 0.93, fingerprint=key, seconds_ago=1)

        engine._buffer[key].append(stale)
        engine._buffer[key].append(fresh)

        engine._prune(key)

        assert len(engine._buffer[key]) == 1
        assert engine._buffer[key][0].node_id == "org_new"

    def test_severity_classification_compatibility(self, engine: CorrelationEngine):
        assert engine._classify_severity(0.97, 3) == "CRITICAL"
        assert engine._classify_severity(0.91, 4) == "HIGH"
        assert engine._classify_severity(0.82, 3) == "MEDIUM"
        assert engine._classify_severity(0.40, 1) == "LOW"


class TestCorrelatorServiceCompatibility:
    @pytest.mark.asyncio
    async def test_service_returns_no_alert_below_threshold(
        self,
        correlator: CorrelatorService,
    ):
        result = await correlator.ingest_signal(
            node_id="org_1",
            timestamp=datetime.now(timezone.utc),
            anomaly_score=0.91,
            fingerprint="AUTH_FAIL_BURST",
            confidence=1.0,
        )

        assert result.accepted is True
        assert result.alert_triggered is False
        assert result.correlation_key == "AUTH_FAIL_BURST"
        assert result.distinct_node_count == 1
        assert result.alert is None

    @pytest.mark.asyncio
    async def test_service_returns_alert_once_threshold_is_met(
        self,
        correlator: CorrelatorService,
    ):
        await correlator.ingest_signal(
            node_id="org_1",
            timestamp=datetime.now(timezone.utc),
            anomaly_score=0.92,
            fingerprint="AUTH_FAIL_BURST",
            confidence=1.0,
        )
        await correlator.ingest_signal(
            node_id="org_2",
            timestamp=datetime.now(timezone.utc),
            anomaly_score=0.89,
            fingerprint="AUTH_FAIL_BURST",
            confidence=0.95,
        )
        result = await correlator.ingest_signal(
            node_id="org_3",
            timestamp=datetime.now(timezone.utc),
            anomaly_score=0.87,
            fingerprint="AUTH_FAIL_BURST",
            confidence=0.9,
        )

        assert result.accepted is True
        assert result.alert_triggered is True
        assert result.correlation_key == "AUTH_FAIL_BURST"
        assert result.distinct_node_count == 3
        assert result.severity in {"MEDIUM", "HIGH", "CRITICAL"}
        assert result.alert is not None
        assert result.alert["fingerprint"] == "AUTH_FAIL_BURST"
        assert result.alert["node_count"] == 3
        assert sorted(result.alert["contributing_nodes"]) == ["org_1", "org_2", "org_3"]
        assert result.alert["status"] == "open"
        assert result.alert["schema_version"] == "1.0"

    def test_build_alert_payload_matches_contract(self, correlator: CorrelatorService):
        payload = correlator.build_alert_payload(
            fingerprint="TRAFFIC_SPIKE",
            contributing_nodes=["org_2", "org_5", "org_7"],
            anomaly_score=0.9032,
            severity="HIGH",
            timestamp=datetime(2026, 3, 21, 10, 5, 15, tzinfo=timezone.utc),
        )

        assert payload["alert_id"].startswith("alt_")
        assert payload["timestamp"] == "2026-03-21T10:05:15+00:00"
        assert payload["severity"] == "HIGH"
        assert payload["fingerprint"] == "TRAFFIC_SPIKE"
        assert payload["anomaly_score"] == 0.903
        assert payload["node_count"] == 3
        assert payload["contributing_nodes"] == ["org_2", "org_5", "org_7"]
        assert payload["status"] == "open"
        assert payload["schema_version"] == "1.0"
        assert "Distributed" in payload["description"]

    def test_build_alert_payload_uses_general_fallback(self, correlator: CorrelatorService):
        payload = correlator.build_alert_payload(
            fingerprint=None,
            contributing_nodes=["org_1", "org_4", "org_9"],
            anomaly_score=0.81,
            severity="MEDIUM",
        )

        assert payload["fingerprint"] is None
        assert payload["node_count"] == 3
        assert payload["severity"] == "MEDIUM"
        assert payload["schema_version"] == "1.0"
        assert "anomalous activity" in payload["description"].lower()

    @pytest.mark.asyncio
    async def test_ingest_record_accepts_prebuilt_signal_record(
        self,
        correlator: CorrelatorService,
    ):
        record = _record("org_42", 0.84, fingerprint="PORT_SCAN_LIKE", confidence=0.88)

        result = await correlator.ingest_record(record)

        assert result.accepted is True
        assert result.correlation_key == "PORT_SCAN_LIKE"
        assert result.distinct_node_count == 1
        assert result.alert_triggered is False
