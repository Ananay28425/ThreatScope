"""
Unit tests for `node_simulator/signal_sender.py` privacy guarantees.

Goal:
- Ensure the composed outbound signal payload contains only sanitized,
  aggregated data.
- Ensure obvious raw-event fields are never present at the top level or
  inside `metrics`.

These tests intentionally mock network I/O and the node pipeline so they
validate the sender contract without requiring a running backend.
"""

from __future__ import annotations

from datetime import datetime, timezone

from node_simulator import signal_sender
from node_simulator.detector import DetectionResult
from node_simulator.feature_extractor import FeatureVector


def _sample_feature_vector() -> FeatureVector:
    return FeatureVector(
        request_rate=42.5,
        failed_login_rate=0.37,
        unique_ip_count=18,
        ip_entropy=2.41,
        error_rate_4xx=0.12,
        error_rate_5xx=0.03,
        avg_response_time_ms=187.4,
        window_seconds=60,
    )


def _sample_detection_result() -> DetectionResult:
    return DetectionResult(
        anomaly_score=0.91,
        fingerprint="AUTH_FAIL_BURST",
        confidence=0.96,
        is_anomalous=True,
        rule_triggered=True,
    )


def test_signal_sender_does_not_send_raw_fields(monkeypatch):
    """
    The sender must only emit derived signal data.

    This test runs one sender loop iteration and captures the HTTP payload
    that would be sent to the backend. It then asserts that common raw-data
    fields never appear in the outbound body.
    """
    captured = {}

    class FakeResponse:
        status_code = 202
        text = "accepted"

    class FakeLogGenerator:
        def __init__(self, *args, **kwargs):
            pass

        def stream(self, interval_seconds):
            yield [
                object(),
                object(),
                object(),
            ]
            return

    class FakeDetector:
        def detect(self, fv):
            return _sample_detection_result()

    def fake_extract_features(raw_events, window_seconds=60):
        return _sample_feature_vector()

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        raise SystemExit("stop after first send")

    monkeypatch.setattr(signal_sender, "LogGenerator", FakeLogGenerator)
    monkeypatch.setattr(signal_sender, "LocalDetector", FakeDetector)
    monkeypatch.setattr(signal_sender, "extract_features", fake_extract_features)
    monkeypatch.setattr(signal_sender.requests, "post", fake_post)

    try:
        signal_sender.run_node(
            node_id="org_test",
            api_key="dev-key",
            interval_seconds=0.01,
            window_seconds=60,
        )
    except SystemExit:
        pass

    payload = captured["json"]

    assert payload["node_id"] == "org_test"
    assert payload["anomaly_score"] == 0.91
    assert payload["fingerprint"] == "AUTH_FAIL_BURST"
    assert payload["confidence"] == 0.96
    assert payload["window_seconds"] == 60
    assert "metrics" in payload
    assert isinstance(payload["metrics"], dict)

    forbidden_top_level = {
        "raw_events",
        "events",
        "logs",
        "raw_logs",
        "source_ip",
        "ip_address",
        "username",
        "password",
        "payload",
        "endpoint",
        "status_code",
        "response_time_ms",
        "is_failed_auth",
    }

    forbidden_metric_keys = {
        "user_id",
        "username",
        "password",
        "payload",
        "ip",
        "ip_address",
        "source_ip",
        "endpoint",
        "status_code",
        "response_time_ms",
        "raw_events",
        "logs",
    }

    assert forbidden_top_level.isdisjoint(payload.keys())
    assert forbidden_metric_keys.isdisjoint(payload["metrics"].keys())


def test_signal_sender_metrics_are_aggregated_only():
    """
    FeatureVector.to_dict() should expose only aggregate metrics that are
    safe to transmit.
    """
    metrics = _sample_feature_vector().to_dict()

    expected_keys = {
        "request_rate",
        "failed_login_rate",
        "unique_ip_count",
        "ip_entropy",
        "error_rate_4xx",
        "error_rate_5xx",
        "avg_response_time_ms",
        "window_seconds",
    }

    forbidden_keys = {
        "source_ip",
        "ip_address",
        "username",
        "password",
        "payload",
        "endpoint",
        "status_code",
        "raw_event",
        "raw_events",
    }

    assert set(metrics.keys()) == expected_keys
    assert forbidden_keys.isdisjoint(metrics.keys())


def test_signal_sender_payload_shape_is_privacy_safe():
    """
    Validate the exact intended sender payload shape independent of transport.
    """
    fv = _sample_feature_vector()
    result = _sample_detection_result()

    payload = {
        "node_id": "org_privacy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "anomaly_score": result.anomaly_score,
        "fingerprint": result.fingerprint,
        "confidence": result.confidence,
        "window_seconds": 60,
        "metrics": fv.to_dict(),
    }

    assert set(payload.keys()) == {
        "node_id",
        "timestamp",
        "anomaly_score",
        "fingerprint",
        "confidence",
        "window_seconds",
        "metrics",
    }

    assert isinstance(payload["timestamp"], str)
    assert isinstance(payload["metrics"], dict)
    assert "raw_events" not in payload
    assert "source_ip" not in payload
    assert "password" not in payload
    assert "payload" not in payload["metrics"]
    assert "source_ip" not in payload["metrics"]
