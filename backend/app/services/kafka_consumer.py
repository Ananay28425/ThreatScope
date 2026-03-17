"""
ThreatScope Kafka consumer service.

Consumes the canonical event topics documented in `docs/topics.md`:

- `node_signals`
- `model_updates`

Primary responsibilities:
1. Read privacy-safe node signals from Kafka
2. Validate and normalize payloads
3. Feed signals into the in-process correlation engine
4. Optionally republish correlated alerts via a producer hook
5. Aggregate model updates for future federated / robust workflows

This module is intentionally written so it can be used in two ways:

- Imported by the FastAPI app and started in-process
- Executed as a standalone worker:
    python -m app.services.kafka_consumer

Notes:
- This service does NOT accept raw logs.
- Invalid messages are logged and skipped.
- Duplicate signals should be tolerated by downstream logic.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import structlog
from app.core.config import settings
from app.correlation.engine import SignalRecord, correlation_engine
from app.schemas.schemas import SignalIngest
from kafka import KafkaConsumer

log = structlog.get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _env_str(name: str, default: str) -> str:
    import os

    value = os.getenv(name)
    return value if value else default


def _env_int(name: str, default: int) -> int:
    import os

    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(slots=True)
class KafkaConsumerConfig:
    bootstrap_servers: str
    node_signals_topic: str
    model_updates_topic: str
    group_id: str = "threatscope-correlator"
    client_id: str = "threatscope-kafka-consumer"
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = True
    poll_timeout_ms: int = 1000

    @classmethod
    def from_env(cls) -> "KafkaConsumerConfig":
        return cls(
            bootstrap_servers=_env_str("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            node_signals_topic=_env_str("KAFKA_NODE_SIGNALS_TOPIC", "node_signals"),
            model_updates_topic=_env_str("KAFKA_MODEL_UPDATES_TOPIC", "model_updates"),
            group_id=_env_str("KAFKA_CONSUMER_GROUP_ID", "threatscope-correlator"),
            client_id=_env_str("KAFKA_CLIENT_ID", "threatscope-kafka-consumer"),
            auto_offset_reset=_env_str("KAFKA_AUTO_OFFSET_RESET", "earliest"),
            enable_auto_commit=_env_str("KAFKA_ENABLE_AUTO_COMMIT", "true").lower() == "true",
            poll_timeout_ms=_env_int("KAFKA_POLL_TIMEOUT_MS", 1000),
        )


@dataclass(slots=True)
class ConsumedMessage:
    topic: str
    partition: int
    offset: int
    key: str | None
    payload: dict[str, Any]
    received_at: datetime


class ModelUpdateAggregator:
    """
    Lightweight in-memory aggregator stub.

    This is not a full federated learning implementation.
    It keeps summary state that can be inspected or extended later.
    """

    def __init__(self) -> None:
        self._updates_by_round: dict[int, list[dict[str, Any]]] = {}
        self._last_update_at: datetime | None = None

    def add_update(self, payload: dict[str, Any]) -> dict[str, Any]:
        round_id = int(payload.get("aggregation_round", 0))
        bucket = self._updates_by_round.setdefault(round_id, [])
        bucket.append(payload)
        self._last_update_at = _utcnow()

        sample_count = sum(int(item.get("sample_count", 0)) for item in bucket)
        node_count = len({str(item.get("node_id", "")) for item in bucket if item.get("node_id")})

        summary = {
            "aggregation_round": round_id,
            "update_count": len(bucket),
            "node_count": node_count,
            "sample_count_total": sample_count,
            "last_update_at": self._last_update_at.isoformat(),
        }

        log.info("Model update aggregated", **summary)
        return summary

    @property
    def state(self) -> dict[str, Any]:
        return {
            "rounds": {k: len(v) for k, v in self._updates_by_round.items()},
            "last_update_at": self._last_update_at.isoformat() if self._last_update_at else None,
        }


class ThreatScopeKafkaConsumerService:
    """
    Kafka-backed event consumer for ThreatScope.

    Topic behavior:
    - `node_signals`: validate and feed to the correlation engine
    - `model_updates`: store lightweight aggregation metadata

    The service exposes:
    - `run_forever()` for blocking worker mode
    - `start_in_background()` / `stop()` for embedded app usage
    """

    def __init__(
        self,
        config: KafkaConsumerConfig | None = None,
        *,
        alert_publisher: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.config = config or KafkaConsumerConfig.from_env()
        self.alert_publisher = alert_publisher
        self.model_aggregator = ModelUpdateAggregator()

        self._consumer: KafkaConsumer | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._started = False

    @property
    def subscribed_topics(self) -> list[str]:
        return [
            self.config.node_signals_topic,
            self.config.model_updates_topic,
        ]

    def build_consumer(self) -> KafkaConsumer:
        """
        Construct the Kafka consumer.

        We deserialize values as JSON and leave message keys as UTF-8 strings.
        """
        return KafkaConsumer(
            *self.subscribed_topics,
            bootstrap_servers=self.config.bootstrap_servers,
            group_id=self.config.group_id,
            client_id=self.config.client_id,
            auto_offset_reset=self.config.auto_offset_reset,
            enable_auto_commit=self.config.enable_auto_commit,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
            consumer_timeout_ms=self.config.poll_timeout_ms,
        )

    def start_in_background(self) -> None:
        if self._started:
            log.info("Kafka consumer already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self.run_forever,
            name="threatscope-kafka-consumer",
            daemon=True,
        )
        self._thread.start()
        self._started = True
        log.info(
            "Kafka consumer background thread started",
            topics=self.subscribed_topics,
            bootstrap_servers=self.config.bootstrap_servers,
        )

    def stop(self, join_timeout: float = 5.0) -> None:
        self._stop_event.set()

        if self._consumer is not None:
            try:
                self._consumer.close()
            except Exception as exc:
                log.warning("Kafka consumer close failed", error=str(exc))

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=join_timeout)

        self._started = False
        log.info("Kafka consumer stopped")

    def run_forever(self) -> None:
        """
        Blocking polling loop.

        Safe to run in a worker container or background thread.
        """
        backoff_seconds = 3

        while not self._stop_event.is_set():
            try:
                self._consumer = self.build_consumer()
                log.info(
                    "Kafka consumer connected",
                    bootstrap_servers=self.config.bootstrap_servers,
                    topics=self.subscribed_topics,
                    group_id=self.config.group_id,
                )

                while not self._stop_event.is_set():
                    records_map = self._consumer.poll(timeout_ms=self.config.poll_timeout_ms)
                    if not records_map:
                        continue

                    for topic_partition, records in records_map.items():
                        for record in records:
                            message = self._to_consumed_message(record)
                            self._handle_message(message)

            except Exception as exc:
                log.error(
                    "Kafka consumer loop failed",
                    error=str(exc),
                    bootstrap_servers=self.config.bootstrap_servers,
                )
                if self._stop_event.is_set():
                    break
                time.sleep(backoff_seconds)
            finally:
                if self._consumer is not None:
                    try:
                        self._consumer.close()
                    except Exception:
                        pass
                    self._consumer = None

    def _to_consumed_message(self, record: Any) -> ConsumedMessage:
        payload = record.value if isinstance(record.value, dict) else {}
        return ConsumedMessage(
            topic=record.topic,
            partition=record.partition,
            offset=record.offset,
            key=record.key,
            payload=payload,
            received_at=_utcnow(),
        )

    def _handle_message(self, message: ConsumedMessage) -> None:
        try:
            if message.topic == self.config.node_signals_topic:
                self._handle_node_signal(message)
            elif message.topic == self.config.model_updates_topic:
                self._handle_model_update(message)
            else:
                log.warning(
                    "Received message for unexpected topic",
                    topic=message.topic,
                    partition=message.partition,
                    offset=message.offset,
                )
        except Exception as exc:
            log.error(
                "Message handling failed",
                topic=message.topic,
                partition=message.partition,
                offset=message.offset,
                error=str(exc),
            )

    def _handle_node_signal(self, message: ConsumedMessage) -> None:
        """
        Validate a `node_signals` payload and forward it to the correlation engine.
        """
        signal = self._normalize_signal_payload(message.payload)

        record = SignalRecord(
            node_id=signal.node_id,
            timestamp=signal.timestamp,
            anomaly_score=signal.anomaly_score,
            fingerprint=signal.fingerprint,
            confidence=signal.confidence,
        )

        self._run_async(correlation_engine.ingest(record))

        log.info(
            "Node signal consumed",
            topic=message.topic,
            partition=message.partition,
            offset=message.offset,
            node_id=signal.node_id,
            fingerprint=signal.fingerprint,
            anomaly_score=signal.anomaly_score,
            confidence=signal.confidence,
        )

    def _handle_model_update(self, message: ConsumedMessage) -> None:
        """
        Process model update metadata.

        For now this is a robust stub that validates the basic contract,
        records summary state, and logs the aggregation result.
        """
        payload = message.payload
        self._validate_model_update_payload(payload)
        summary = self.model_aggregator.add_update(payload)

        log.info(
            "Model update consumed",
            topic=message.topic,
            partition=message.partition,
            offset=message.offset,
            node_id=payload.get("node_id"),
            model_version=payload.get("model_version"),
            aggregation_round=payload.get("aggregation_round"),
            summary=summary,
        )

    def _normalize_signal_payload(self, payload: dict[str, Any]) -> SignalIngest:
        """
        Accept canonical Kafka payloads and convert them into the existing
        backend validation model.

        Expected Kafka shape may include:
        - signal_id
        - schema_version
        - transport
        - node_id
        - timestamp
        - anomaly_score
        - confidence
        - fingerprint
        - window_seconds
        - metrics
        """
        normalized = {
            "node_id": payload.get("node_id"),
            "timestamp": payload.get("timestamp"),
            "anomaly_score": payload.get("anomaly_score"),
            "fingerprint": payload.get("fingerprint"),
            "confidence": payload.get("confidence", 1.0),
            "window_seconds": payload.get("window_seconds", 60),
            "metrics": payload.get("metrics"),
        }

        try:
            return SignalIngest.model_validate(normalized)
        except Exception as exc:
            raise ValueError(f"Invalid node_signals payload: {exc}") from exc

    def _validate_model_update_payload(self, payload: dict[str, Any]) -> None:
        required_fields = (
            "update_id",
            "node_id",
            "timestamp",
            "model_version",
            "aggregation_round",
            "sample_count",
            "update_type",
            "payload",
            "schema_version",
        )

        missing = [field for field in required_fields if field not in payload]
        if missing:
            raise ValueError(f"Model update missing required fields: {missing}")

        if not isinstance(payload["payload"], dict):
            raise ValueError("Model update field `payload` must be an object")

        try:
            datetime.fromisoformat(str(payload["timestamp"]).replace("Z", "+00:00"))
        except Exception as exc:
            raise ValueError("Model update timestamp must be RFC 3339 / ISO 8601") from exc

        try:
            aggregation_round = int(payload["aggregation_round"])
            sample_count = int(payload["sample_count"])
        except Exception as exc:
            raise ValueError("Model update numeric fields are invalid") from exc

        if aggregation_round < 0:
            raise ValueError("Model update aggregation_round must be non-negative")
        if sample_count <= 0:
            raise ValueError("Model update sample_count must be positive")

    @staticmethod
    def _run_async(coro: Any) -> None:
        """
        Execute an async coroutine from synchronous Kafka consumer code.

        This works for standalone worker execution. If the service is later
        embedded into an already-running async app, this can be swapped for a
        queue handoff or loop-safe scheduler.
        """
        asyncio.run(coro)


consumer_service = ThreatScopeKafkaConsumerService()


def main() -> None:
    log.info(
        "Starting ThreatScope Kafka consumer service",
        bootstrap_servers=consumer_service.config.bootstrap_servers,
        topics=consumer_service.subscribed_topics,
        app_env=settings.app_env,
    )
    try:
        consumer_service.run_forever()
    except KeyboardInterrupt:
        log.info("Kafka consumer interrupted by user")
    finally:
        consumer_service.stop()


if __name__ == "__main__":
    main()
