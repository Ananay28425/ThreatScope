"""Regression tests for actual observation duration and warmup rule preservation."""
from common.contracts import utcnow
from node_simulator.detector import LocalDetector
from node_simulator.scenarios import catalogue_values, events_for


def test_actual_window_duration():
    events = events_for("auth_attack", 42, 5, utcnow())
    features, _ = catalogue_values(events, 5)
    assert features.request_rate == 200


def test_rule_survives_warmup_and_attacks_not_used_as_clean_baseline():
    events = events_for("auth_attack", 42, 10, utcnow())
    features, _ = catalogue_values(events, 10)
    detector = LocalDetector()
    result = detector.detect(features)
    assert result.anomaly_score >= 0.8 and result.is_anomalous
    assert detector._baseline == []


def test_benign_outage_can_trigger_local_rule_but_has_distinct_evidence():
    events = events_for("provider_outage", 42, 10, utcnow())
    features, values = catalogue_values(events, 10)
    assert LocalDetector().detect(features).is_anomalous
    assert values["failure_kind"] == "unavailable"
