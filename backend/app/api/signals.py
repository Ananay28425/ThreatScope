"""
Backend signal ingestion API module for ThreatScope.

This module provides a FastAPI router that:
  - validates privacy-safe signal payloads
  - authenticates node agents with a simple API-key stub
  - increments Prometheus metrics
  - forwards signals into the in-memory correlation engine
  - emits a lightweight signal pulse event over WebSocket for the frontend

It is intentionally compatible with the current codebase layout while also
matching the requested repository structure (`app/api/signals.py`).
"""

from datetime import datetime, timezone

import structlog
from app.correlation.engine import SignalRecord, correlation_engine
from app.metrics.prometheus import signals_ingested_total
from app.schemas.schemas import SignalIngest
from fastapi import APIRouter, Depends, Header, HTTPException, status

router = APIRouter(prefix="/api/signals", tags=["signals"])
log = structlog.get_logger(__name__)


async def verify_node_api_key(x_api_key: str = Header(...)) -> str:
    """
    Validate the node API key.

    Current behavior is a development stub:
      - requires a non-empty `X-Api-Key` header
      - returns the header value as the authenticated node identity

    Later this should be replaced with:
      - hashed API-key lookup in the database
      - node status checks
      - rate limiting / revocation controls
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    return x_api_key.strip()


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(
    signal: SignalIngest,
    authenticated_node_id: str = Depends(verify_node_api_key),
) -> dict:
    """
    Accept a privacy-preserving signal from a node and route it for processing.

    Notes:
      - The payload is expected to contain only derived, non-raw metrics.
      - The API key identity is treated as authoritative for the sender.
      - If `signal.node_id` differs from the authenticated identity, the
        authenticated identity wins for backend processing and auditing.
    """
    effective_node_id = authenticated_node_id

    signals_ingested_total.labels(
        node_id=effective_node_id,
        fingerprint=signal.fingerprint or "unknown",
    ).inc()

    record = SignalRecord(
        node_id=effective_node_id,
        timestamp=signal.timestamp,
        anomaly_score=signal.anomaly_score,
        fingerprint=signal.fingerprint,
        confidence=signal.confidence,
    )
    await correlation_engine.ingest(record)

    if correlation_engine.broadcast:
        await correlation_engine.broadcast(
            {
                "event_type": "signal_pulse",
                "payload": {
                    "node_id": effective_node_id,
                    "timestamp": signal.timestamp.astimezone(timezone.utc).isoformat(),
                    "anomaly_score": signal.anomaly_score,
                    "fingerprint": signal.fingerprint,
                    "confidence": signal.confidence,
                    "window_seconds": signal.window_seconds,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    log.info(
        "Signal ingested",
        authenticated_node_id=authenticated_node_id,
        payload_node_id=signal.node_id,
        effective_node_id=effective_node_id,
        score=signal.anomaly_score,
        fingerprint=signal.fingerprint,
        confidence=signal.confidence,
    )

    return {
        "status": "accepted",
        "node_id": effective_node_id,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
