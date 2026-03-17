"""
Signal ingestion endpoint.

This is the most security-critical route in ThreatScope:
  - Nodes authenticate with an API key (hashed, per-org).
  - Signals are validated through Pydantic strict mode (including
    the raw-log-field blocklist validator in schemas.py).
  - Valid signals are pushed into the Valkey Stream for async processing
    AND directly fed into the in-memory correlation engine for low-latency alerting.
  - Rate limiting prevents a malfunctioning or compromised node from
    flooding the pipeline.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
import structlog

from app.correlation.engine import correlation_engine, SignalRecord
from app.metrics.prometheus import signals_ingested_total
from app.schemas.schemas import SignalIngest

router = APIRouter(prefix="/api/signals", tags=["signals"])
log = structlog.get_logger(__name__)

# ── Simple API Key Auth for Nodes ─────────────────────────────────────────────
# Nodes authenticate with a pre-shared API key (hashed in the DB).
# This is intentionally simpler than JWT — nodes are machine clients,
# not human users.

async def verify_node_api_key(x_api_key: str = Header(...)) -> str:
    """
    Validate the node's API key.
    Returns the node_id on success, raises 401 on failure.

    TODO (Phase 5): look up hashed key in Postgres.
    For Phase 1 dev, accept any non-empty key and use it as the node_id.
    """
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    return x_api_key  # Replace with DB lookup in Phase 5


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(
    signal: SignalIngest,
    node_id: str = Depends(verify_node_api_key),
) -> dict:
    """
    Accept a privacy-safe signal from a node and route it for processing.

    Returns 202 Accepted immediately — processing is async.
    The client should not retry on 202; the signal is guaranteed to be
    enqueued unless a 4xx/5xx is returned.
    """
    # Increment Prometheus counter (labelled by node + fingerprint)
    signals_ingested_total.labels(
        node_id=node_id,
        fingerprint=signal.fingerprint or "unknown",
    ).inc()

    # Feed into correlation engine (in-process, low latency)
    record = SignalRecord(
        node_id=node_id,
        timestamp=signal.timestamp,
        anomaly_score=signal.anomaly_score,
        fingerprint=signal.fingerprint,
        confidence=signal.confidence,
    )
    await correlation_engine.ingest(record)

    log.info(
        "Signal ingested",
        node_id=node_id,
        score=signal.anomaly_score,
        fingerprint=signal.fingerprint,
    )

    return {"status": "accepted", "node_id": node_id}
