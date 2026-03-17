"""
Correlation Engine — the "brain" of ThreatScope.

Responsibility: aggregate signals arriving from multiple independent nodes
within a configurable sliding time window, and raise a GLOBAL_ALERT when
enough nodes report matching high-anomaly-score events.

Why this matters architecturally:
  A single node reporting a high anomaly score could be a false positive
  (misconfigured service, maintenance window, etc.).
  Three or more nodes reporting the same fingerprint within 120 seconds
  is statistically near-impossible unless there's a real distributed attack.

This replaces the originally planned federated ML training with a simpler,
more reliable rule-based correlation — correct engineering tradeoff for
a final-year project timeline.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import structlog

from app.core.config import settings
from app.schemas.schemas import WSEvent

log = structlog.get_logger(__name__)


class SignalRecord(NamedTuple):
    node_id: str
    timestamp: datetime
    anomaly_score: float
    fingerprint: str | None
    confidence: float


class CorrelationEngine:
    """
    In-memory sliding-window correlation engine.

    Design notes:
    - Signals are stored in a dict keyed by fingerprint → list of recent records.
    - On each new signal, the engine prunes stale records (outside the window),
      then checks if the threshold is met.
    - This is intentionally stateless between restarts — Valkey Streams
      provide durability; the engine can rebuild state from the stream on startup.
    - Thread safety: use asyncio.Lock because FastAPI runs in an async event loop.
    """

    def __init__(self) -> None:
        # fingerprint → list of recent SignalRecords within the window
        self._buffer: dict[str, list[SignalRecord]] = defaultdict(list)
        self._lock = asyncio.Lock()
        # Injected by the app startup: callable that sends WS events to all clients
        self.broadcast: callable | None = None

    async def ingest(self, record: SignalRecord) -> None:
        """Accept a new signal and evaluate correlation conditions."""
        async with self._lock:
            key = record.fingerprint or "_general"
            self._buffer[key].append(record)
            self._prune(key)
            await self._evaluate(key)

    def _prune(self, key: str) -> None:
        """Remove records outside the sliding window."""
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=settings.correlation_window_seconds
        )
        self._buffer[key] = [
            r for r in self._buffer[key] if r.timestamp >= cutoff
        ]

    async def _evaluate(self, key: str) -> None:
        """
        Raise a global alert if correlation thresholds are met.

        Conditions (all must hold):
          1. ≥ N distinct nodes reported signals (default N=3)
          2. All those signals have anomaly_score ≥ threshold (default 0.80)
          3. All within the correlation window (enforced by _prune above)

        The confidence-weighted scoring is an optional extension that makes
        the system more robust against a single misconfigured node artificially
        inflating scores.
        """
        records = self._buffer[key]

        # Filter to only high-score signals
        high = [r for r in records if r.anomaly_score >= settings.alert_threshold_score]

        # Deduplicate by node — we want distinct nodes, not duplicate signals
        unique_nodes = {r.node_id for r in high}

        if len(unique_nodes) < settings.alert_threshold_nodes:
            return  # Not enough corroborating nodes yet

        # Compute confidence-weighted mean score
        total_confidence = sum(r.confidence for r in high)
        weighted_score = (
            sum(r.anomaly_score * r.confidence for r in high) / total_confidence
            if total_confidence > 0
            else 0.0
        )

        severity = self._classify_severity(weighted_score, len(unique_nodes))

        log.warning(
            "GLOBAL ALERT triggered",
            fingerprint=key,
            nodes=list(unique_nodes),
            weighted_score=round(weighted_score, 3),
            severity=severity,
        )

        # Broadcast to all connected WebSocket clients
        if self.broadcast:
            event = WSEvent(
                event_type="new_alert",
                payload={
                    "fingerprint": key,
                    "severity": severity,
                    "contributing_nodes": list(unique_nodes),
                    "anomaly_score": round(weighted_score, 3),
                    "node_count": len(unique_nodes),
                },
                timestamp=datetime.now(timezone.utc),
            )
            await self.broadcast(event.model_dump(mode="json"))

    @staticmethod
    def _classify_severity(score: float, node_count: int) -> str:
        """
        Map weighted score + contributing node count to severity level.

        The dual-axis approach (score AND breadth) is key:
        a score of 0.85 from 10 nodes is far more serious than from 3.
        """
        if score >= 0.95 or node_count >= 8:
            return "CRITICAL"
        elif score >= 0.90 or node_count >= 6:
            return "HIGH"
        elif score >= 0.80 or node_count >= 3:
            return "MEDIUM"
        return "LOW"


# ── Module-level singleton ────────────────────────────────────────────────────
correlation_engine = CorrelationEngine()
