"""
Celery background tasks for ThreatScope.

Workers run in a separate container from the FastAPI server.
They handle work that is too heavy or too slow for the request-response cycle:
  - Periodic alert aggregation (roll-up summaries for Grafana)
  - Correlation window cleanup (flush stale signal buffer entries)
  - Potential future: offline model retraining triggers

Celery connects to Valkey as its broker (FOSS, BSD-3-Clause).
redis-py 5.x is fully compatible with Valkey — no code changes needed.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

# ── Celery App ────────────────────────────────────────────────────────────────

celery_app = Celery(
    "threatscope",
    broker=settings.celery_broker_url,       # redis://valkey:6379/1
    backend=settings.celery_result_backend,  # redis://valkey:6379/2
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # fairness under load
)

# ── Periodic Tasks ────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {
    # Every minute: aggregate alerts from the last hour for Grafana dashboards
    "aggregate-alerts-every-minute": {
        "task": "workers.tasks.aggregate_alerts",
        "schedule": 60.0,
    },
    # Every 5 minutes: clean up the in-memory signal buffer
    "prune-signal-buffer": {
        "task": "workers.tasks.prune_signal_buffer",
        "schedule": 300.0,
    },
}


# ── Task Definitions ──────────────────────────────────────────────────────────

@celery_app.task(name="workers.tasks.aggregate_alerts", bind=True, max_retries=3)
def aggregate_alerts(self) -> dict:
    """
    Roll up the last 60 seconds of alert data for Grafana.
    This task is intentionally lightweight — it reads from Postgres
    and updates a Valkey cache key that Grafana can scrape.
    """
    import redis
    from datetime import datetime, timedelta, timezone

    try:
        client = redis.from_url(settings.valkey_url)
        # Placeholder: in Phase 8 this will query Postgres and write summary to Valkey
        now = datetime.now(timezone.utc).isoformat()
        client.set("threatscope:last_aggregate", now, ex=120)
        return {"status": "ok", "at": now}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="workers.tasks.prune_signal_buffer")
def prune_signal_buffer() -> dict:
    """
    Ask the in-process correlation engine to prune its buffer.
    Note: this only works if the Celery worker runs in the same process as FastAPI.
    For multi-process deployments, move buffer state into Valkey.
    """
    from app.correlation.engine import correlation_engine
    import asyncio

    # Prune all known fingerprint buckets
    pruned = 0
    for key in list(correlation_engine._buffer.keys()):
        before = len(correlation_engine._buffer[key])
        correlation_engine._prune(key)
        pruned += before - len(correlation_engine._buffer[key])

    return {"pruned_records": pruned}
