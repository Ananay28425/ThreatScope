"""
Backend correlator service wrapper for ThreatScope.

This module provides a small service layer around the in-memory
`CorrelationEngine` so the rest of the backend can interact with a stable,
testable API instead of importing engine internals everywhere.

Responsibilities:
- Normalize inbound signal payloads into `SignalRecord`
- Forward records into the core correlation engine
- Build alert payloads suitable for REST, Kafka, or WebSocket publication
- Expose helper methods that future Kafka consumers can call directly

This wrapper does not persist alerts by itself. Persistence and publishing are
left to higher-level workers/routes so the service remains easy to reuse.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.correlation.engine import CorrelationEngine, SignalRecord, correlation_engine


@dataclass(slots=True)
class CorrelationResult:
    """
    Result returned by the service after evaluating a signal.

    Attributes:
        accepted:
            Whether the signal was accepted and processed.
        alert_triggered:
            Whether the current signal caused correlation thresholds to be met.
        correlation_key:
            Fingerprint used for grouping. Falls back to `_general`.
        distinct_node_count:
            Number of distinct nodes currently contributing above threshold.
        weighted_score:
            Confidence-weighted score for the correlated set.
        severity:
            Computed severity if an alert condition is met.
        alert:
            Fully materialized alert payload, or None when no alert fired.
    """

    accepted: bool
    alert_triggered: bool
    correlation_key: str
    distinct_node_count: int
    weighted_score: float
    severity: str | None
    alert: dict[str, Any] | None


class CorrelatorService:
    """
    Thin application service over the core correlation engine.

    The underlying engine already handles pruning, node deduplication,
    threshold checks, and WebSocket broadcast. This service adds:
    - input normalization
    - reusable alert payload construction
    - a clearer interface for route handlers and Kafka consumers
    """

    def __init__(self, engine: CorrelationEngine | None = None) -> None:
        self.engine = engine or correlation_engine

    async def ingest_signal(
        self,
        *,
        node_id: str,
        timestamp: datetime,
        anomaly_score: float,
        fingerprint: str | None,
        confidence: float = 1.0,
    ) -> CorrelationResult:
        """
        Normalize a signal and pass it into the correlation engine.

        Returns a `CorrelationResult` describing the current correlated state
        after ingestion. The core engine remains responsible for live broadcast.
        """
        record = SignalRecord(
            node_id=node_id,
            timestamp=self._ensure_utc(timestamp),
            anomaly_score=float(anomaly_score),
            fingerprint=fingerprint,
            confidence=float(confidence),
        )

        await self.engine.ingest(record)
        return self._build_result(record)

    async def ingest_record(self, record: SignalRecord) -> CorrelationResult:
        """
        Ingest a pre-built `SignalRecord`.

        Useful for internal callers that already converted upstream payloads.
        """
        normalized = SignalRecord(
            node_id=record.node_id,
            timestamp=self._ensure_utc(record.timestamp),
            anomaly_score=float(record.anomaly_score),
            fingerprint=record.fingerprint,
            confidence=float(record.confidence),
        )
        await self.engine.ingest(normalized)
        return self._build_result(normalized)

    def build_alert_payload(
        self,
        *,
        fingerprint: str | None,
        contributing_nodes: list[str],
        anomaly_score: float,
        severity: str,
        timestamp: datetime | None = None,
        status: str = "open",
    ) -> dict[str, Any]:
        """
        Build a canonical alert payload for downstream systems.

        This shape is intentionally compatible with the documented `alerts`
        topic contract and also works well as a REST/WebSocket payload.
        """
        correlation_key = fingerprint or "_general"
        event_time = self._ensure_utc(timestamp or datetime.now(timezone.utc))
        node_count = len(contributing_nodes)

        return {
            "alert_id": f"alt_{uuid4().hex}",
            "timestamp": event_time.isoformat(),
            "severity": severity,
            "fingerprint": None if correlation_key == "_general" else correlation_key,
            "anomaly_score": round(float(anomaly_score), 3),
            "node_count": node_count,
            "contributing_nodes": contributing_nodes,
            "status": status,
            "description": self._build_description(
                fingerprint=None if correlation_key == "_general" else correlation_key,
                node_count=node_count,
                window_seconds=settings.correlation_window_seconds,
            ),
            "correlation_window_seconds": settings.correlation_window_seconds,
            "schema_version": "1.0",
        }

    def _build_result(self, record: SignalRecord) -> CorrelationResult:
        """
        Inspect engine state after ingestion and return a structured result.
        """
        key = record.fingerprint or "_general"
        records = self.engine._buffer.get(key, [])

        high = [r for r in records if r.anomaly_score >= settings.alert_threshold_score]
        unique_nodes = sorted({r.node_id for r in high})

        if not unique_nodes:
            return CorrelationResult(
                accepted=True,
                alert_triggered=False,
                correlation_key=key,
                distinct_node_count=0,
                weighted_score=0.0,
                severity=None,
                alert=None,
            )

        total_confidence = sum(r.confidence for r in high)
        weighted_score = (
            sum(r.anomaly_score * r.confidence for r in high) / total_confidence
            if total_confidence > 0
            else 0.0
        )

        alert_triggered = len(unique_nodes) >= settings.alert_threshold_nodes
        severity = (
            self.engine._classify_severity(weighted_score, len(unique_nodes))
            if alert_triggered
            else None
        )

        alert = (
            self.build_alert_payload(
                fingerprint=None if key == "_general" else key,
                contributing_nodes=unique_nodes,
                anomaly_score=weighted_score,
                severity=severity,
            )
            if alert_triggered and severity is not None
            else None
        )

        return CorrelationResult(
            accepted=True,
            alert_triggered=alert_triggered,
            correlation_key=key,
            distinct_node_count=len(unique_nodes),
            weighted_score=round(weighted_score, 4),
            severity=severity,
            alert=alert,
        )

    @staticmethod
    def _build_description(
        *,
        fingerprint: str | None,
        node_count: int,
        window_seconds: int,
    ) -> str:
        """
        Generate a human-readable alert summary.
        """
        if fingerprint:
            label = fingerprint.replace("_", " ").title()
            return (
                f"Distributed {label} pattern detected across "
                f"{node_count} node(s) within {window_seconds} seconds."
            )
        return (
            f"Distributed anomalous activity detected across "
            f"{node_count} node(s) within {window_seconds} seconds."
        )

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        """
        Ensure datetimes are timezone-aware UTC values.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


correlator_service = CorrelatorService()
