"""
ThreatScope aggregation service.

This module provides a lightweight, backend-side model update aggregation layer
for the `model_updates` topic described in the project docs.

Design goals:
- Keep the implementation simple and demo-friendly
- Support multiple aggregation strategies:
  - weighted mean / FedAvg
  - coordinate-wise median
  - trimmed mean
- Validate incoming updates conservatively
- Be safe by default when no valid updates are available
- Return rich metadata useful for logging, persistence, or publishing

This service does NOT assume any specific ML framework. Updates are represented
as numeric vectors and optional metadata. That makes it flexible enough for:
- distilled feature summaries
- compact model parameter snapshots
- synthetic demo payloads
- future robust aggregation experiments

Example payload shape expected by this service:

{
    "update_id": "upd_123",
    "node_id": "org_1",
    "timestamp": "2026-03-21T10:05:00Z",
    "model_version": "iforest_v2",
    "aggregation_round": 4,
    "sample_count": 1250,
    "update_type": "fedavg",
    "payload": {
        "weights": [0.1, 0.2, 0.3],
        "bias": 0.4
    },
    "quality_score": 0.93,
    "node_weight": 1.0,
    "schema_version": "1.0"
}

The service normalizes payloads into flat numeric vectors before aggregation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median
from typing import Any, Iterable, Literal, Sequence

AggregationMethod = Literal["fedavg", "weighted_mean", "median", "trimmed_mean"]


@dataclass(slots=True)
class ModelUpdate:
    """
    Canonical internal representation of an incoming model update.
    """

    update_id: str
    node_id: str
    timestamp: datetime
    model_version: str
    aggregation_round: int
    sample_count: int
    update_type: str
    payload: dict[str, Any]
    schema_version: str = "1.0"
    quality_score: float = 1.0
    node_weight: float = 1.0


@dataclass(slots=True)
class AggregatedModel:
    """
    Result returned by the aggregation service.
    """

    aggregation_id: str
    method: AggregationMethod
    aggregation_round: int
    model_version: str
    participant_count: int
    accepted_updates: int
    rejected_updates: int
    created_at: datetime
    vector_keys: list[str]
    aggregated_vector: list[float]
    payload: dict[str, float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AggregationBatch:
    """
    Container for a batch of updates to aggregate together.
    """

    updates: list[ModelUpdate]
    round_id: int | None = None
    model_version: str | None = None


class AggregationError(ValueError):
    """
    Raised when aggregation input is invalid or unsafe to process.
    """


class UpdateValidationError(ValueError):
    """
    Raised when a single incoming update fails validation.
    """


class AggregatorService:
    """
    Backend aggregation service for model updates.

    Capabilities:
    - validates incoming updates
    - flattens payload dictionaries into stable numeric vectors
    - aggregates by weighted average, median, or trimmed mean
    - computes summary metadata about the batch

    Notes:
    - This is intentionally framework-agnostic.
    - Payload flattening is deterministic by sorted key traversal.
    - Nested dictionaries and numeric sequences are supported.
    - Non-numeric values are rejected.
    """

    SUPPORTED_METHODS: tuple[AggregationMethod, ...] = (
        "fedavg",
        "weighted_mean",
        "median",
        "trimmed_mean",
    )

    def __init__(
        self,
        default_method: AggregationMethod = "fedavg",
        min_updates: int = 1,
        trim_ratio: float = 0.1,
        max_vector_length: int = 100_000,
    ) -> None:
        if default_method not in self.SUPPORTED_METHODS:
            raise AggregationError(f"Unsupported default aggregation method: {default_method}")
        if min_updates < 1:
            raise AggregationError("min_updates must be >= 1")
        if not 0.0 <= trim_ratio < 0.5:
            raise AggregationError("trim_ratio must be within [0.0, 0.5)")
        if max_vector_length < 1:
            raise AggregationError("max_vector_length must be >= 1")

        self.default_method = default_method
        self.min_updates = min_updates
        self.trim_ratio = trim_ratio
        self.max_vector_length = max_vector_length

    def parse_update(self, raw: dict[str, Any]) -> ModelUpdate:
        """
        Parse a raw dict into a validated `ModelUpdate`.
        """
        required = {
            "update_id",
            "node_id",
            "timestamp",
            "model_version",
            "aggregation_round",
            "sample_count",
            "update_type",
            "payload",
        }
        missing = required - set(raw.keys())
        if missing:
            raise UpdateValidationError(f"Missing required update fields: {sorted(missing)}")

        timestamp = self._parse_timestamp(raw["timestamp"])
        update = ModelUpdate(
            update_id=str(raw["update_id"]),
            node_id=str(raw["node_id"]),
            timestamp=timestamp,
            model_version=str(raw["model_version"]),
            aggregation_round=int(raw["aggregation_round"]),
            sample_count=int(raw["sample_count"]),
            update_type=str(raw["update_type"]),
            payload=self._require_payload_dict(raw["payload"]),
            schema_version=str(raw.get("schema_version", "1.0")),
            quality_score=float(raw.get("quality_score", 1.0)),
            node_weight=float(raw.get("node_weight", 1.0)),
        )
        self.validate_update(update)
        return update

    def validate_update(self, update: ModelUpdate) -> None:
        """
        Validate one update conservatively.
        """
        if not update.update_id.strip():
            raise UpdateValidationError("update_id must not be empty")
        if not update.node_id.strip():
            raise UpdateValidationError("node_id must not be empty")
        if not update.model_version.strip():
            raise UpdateValidationError("model_version must not be empty")
        if update.aggregation_round < 0:
            raise UpdateValidationError("aggregation_round must be non-negative")
        if update.sample_count <= 0:
            raise UpdateValidationError("sample_count must be positive")
        if update.quality_score < 0.0 or update.quality_score > 1.0:
            raise UpdateValidationError("quality_score must be within [0.0, 1.0]")
        if update.node_weight < 0.0:
            raise UpdateValidationError("node_weight must be >= 0.0")
        if not isinstance(update.payload, dict) or not update.payload:
            raise UpdateValidationError("payload must be a non-empty object")

        keys, vector = self._flatten_payload(update.payload)
        if not keys or not vector:
            raise UpdateValidationError("payload did not produce a numeric vector")
        if len(vector) > self.max_vector_length:
            raise UpdateValidationError(
                f"payload vector length {len(vector)} exceeds max {self.max_vector_length}"
            )

    def aggregate(
        self,
        updates: Sequence[ModelUpdate | dict[str, Any]],
        method: AggregationMethod | None = None,
    ) -> AggregatedModel:
        """
        Aggregate a batch of updates into a single model artifact description.

        Accepts either already-parsed `ModelUpdate` instances or raw dicts.
        Invalid updates are rejected and counted in the metadata. If no valid
        updates remain, an exception is raised.
        """
        chosen_method = method or self.default_method
        if chosen_method not in self.SUPPORTED_METHODS:
            raise AggregationError(f"Unsupported aggregation method: {chosen_method}")

        accepted: list[ModelUpdate] = []
        rejected: list[dict[str, str]] = []

        for item in updates:
            try:
                update = item if isinstance(item, ModelUpdate) else self.parse_update(item)
                accepted.append(update)
            except Exception as exc:
                rejected.append({"reason": str(exc)})

        if len(accepted) < self.min_updates:
            raise AggregationError(
                f"Need at least {self.min_updates} valid updates, got {len(accepted)}"
            )

        self._ensure_batch_compatibility(accepted)

        vector_keys, matrix = self._build_matrix(accepted)
        weights = [self._effective_weight(u) for u in accepted]

        if chosen_method in ("fedavg", "weighted_mean"):
            aggregated_vector = self._weighted_mean(matrix, weights)
        elif chosen_method == "median":
            aggregated_vector = self._coordinate_median(matrix)
        elif chosen_method == "trimmed_mean":
            aggregated_vector = self._trimmed_mean(matrix, self.trim_ratio)
        else:
            raise AggregationError(f"Unhandled aggregation method: {chosen_method}")

        now = datetime.now(timezone.utc)
        round_id = accepted[0].aggregation_round
        model_version = accepted[0].model_version
        aggregation_id = f"agg_r{round_id}_{int(now.timestamp())}"

        payload = {
            key: value
            for key, value in zip(vector_keys, aggregated_vector, strict=False)
        }

        metadata = {
            "participant_nodes": sorted({u.node_id for u in accepted}),
            "update_ids": [u.update_id for u in accepted],
            "weights": weights,
            "rejections": rejected,
            "source_update_type": accepted[0].update_type,
            "summary": {
                "sample_count_total": sum(u.sample_count for u in accepted),
                "sample_count_min": min(u.sample_count for u in accepted),
                "sample_count_max": max(u.sample_count for u in accepted),
                "quality_score_mean": self._safe_mean([u.quality_score for u in accepted]),
                "node_weight_mean": self._safe_mean([u.node_weight for u in accepted]),
                "vector_length": len(aggregated_vector),
            },
        }

        return AggregatedModel(
            aggregation_id=aggregation_id,
            method=chosen_method,
            aggregation_round=round_id,
            model_version=model_version,
            participant_count=len({u.node_id for u in accepted}),
            accepted_updates=len(accepted),
            rejected_updates=len(rejected),
            created_at=now,
            vector_keys=vector_keys,
            aggregated_vector=aggregated_vector,
            payload=payload,
            metadata=metadata,
        )

    def aggregate_batch(
        self,
        batch: AggregationBatch,
        method: AggregationMethod | None = None,
    ) -> AggregatedModel:
        """
        Convenience wrapper for aggregating an `AggregationBatch`.
        """
        result = self.aggregate(batch.updates, method=method)

        if batch.round_id is not None and result.aggregation_round != batch.round_id:
            raise AggregationError(
                f"Batch round mismatch: expected {batch.round_id}, got {result.aggregation_round}"
            )
        if batch.model_version is not None and result.model_version != batch.model_version:
            raise AggregationError(
                f"Batch model_version mismatch: expected {batch.model_version}, "
                f"got {result.model_version}"
            )

        return result

    def to_publishable_event(self, aggregated: AggregatedModel) -> dict[str, Any]:
        """
        Convert an aggregation result into a JSON-serializable event suitable for:
        - publishing to Kafka
        - storing in a DB
        - exposing via an API response
        """
        return {
            "aggregation_id": aggregated.aggregation_id,
            "method": aggregated.method,
            "aggregation_round": aggregated.aggregation_round,
            "model_version": aggregated.model_version,
            "participant_count": aggregated.participant_count,
            "accepted_updates": aggregated.accepted_updates,
            "rejected_updates": aggregated.rejected_updates,
            "created_at": aggregated.created_at.isoformat(),
            "payload": aggregated.payload,
            "vector_keys": aggregated.vector_keys,
            "metadata": aggregated.metadata,
        }

    def _ensure_batch_compatibility(self, updates: Sequence[ModelUpdate]) -> None:
        """
        Ensure all accepted updates belong to the same round and model version,
        and produce compatible vector schemas.
        """
        rounds = {u.aggregation_round for u in updates}
        if len(rounds) != 1:
            raise AggregationError(f"Updates span multiple aggregation rounds: {sorted(rounds)}")

        versions = {u.model_version for u in updates}
        if len(versions) != 1:
            raise AggregationError(f"Updates span multiple model versions: {sorted(versions)}")

        seen_nodes = [u.node_id for u in updates]
        if len(set(seen_nodes)) != len(seen_nodes):
            raise AggregationError("Duplicate node_id detected in aggregation batch")

        first_keys, _ = self._flatten_payload(updates[0].payload)
        for update in updates[1:]:
            keys, _ = self._flatten_payload(update.payload)
            if keys != first_keys:
                raise AggregationError(
                    "All payloads must flatten to the same ordered feature set"
                )

    def _build_matrix(self, updates: Sequence[ModelUpdate]) -> tuple[list[str], list[list[float]]]:
        keys, _ = self._flatten_payload(updates[0].payload)
        matrix: list[list[float]] = []
        for update in updates:
            _, vector = self._flatten_payload(update.payload)
            matrix.append(vector)
        return keys, matrix

    def _effective_weight(self, update: ModelUpdate) -> float:
        """
        Compute the effective aggregation weight for a single update.

        For demo robustness:
        - sample_count contributes naturally
        - quality_score downweights low-confidence updates
        - node_weight allows external tuning
        """
        base = float(update.sample_count)
        effective = base * max(update.quality_score, 0.0) * max(update.node_weight, 0.0)
        return effective if effective > 0.0 else 0.0

    def _weighted_mean(self, matrix: Sequence[Sequence[float]], weights: Sequence[float]) -> list[float]:
        if not matrix:
            raise AggregationError("Cannot aggregate an empty matrix")

        if len(matrix) != len(weights):
            raise AggregationError("Matrix row count and weight count must match")

        total_weight = sum(weights)
        if total_weight <= 0.0:
            # Fallback to uniform mean if all weights are zero.
            weights = [1.0] * len(matrix)
            total_weight = float(len(matrix))

        width = len(matrix[0])
        result: list[float] = []

        for col in range(width):
            acc = 0.0
            for row, weight in zip(matrix, weights, strict=False):
                acc += row[col] * weight
            result.append(acc / total_weight)

        return result

    def _coordinate_median(self, matrix: Sequence[Sequence[float]]) -> list[float]:
        if not matrix:
            raise AggregationError("Cannot aggregate an empty matrix")

        width = len(matrix[0])
        result: list[float] = []
        for col in range(width):
            column = [row[col] for row in matrix]
            result.append(float(median(column)))
        return result

    def _trimmed_mean(self, matrix: Sequence[Sequence[float]], trim_ratio: float) -> list[float]:
        if not matrix:
            raise AggregationError("Cannot aggregate an empty matrix")

        width = len(matrix[0])
        n = len(matrix)
        trim_count = int(math.floor(n * trim_ratio))

        result: list[float] = []
        for col in range(width):
            column = sorted(row[col] for row in matrix)
            trimmed = column[trim_count : n - trim_count] if trim_count > 0 else column
            if not trimmed:
                trimmed = column
            result.append(sum(trimmed) / len(trimmed))
        return result

    def _flatten_payload(self, payload: dict[str, Any]) -> tuple[list[str], list[float]]:
        """
        Flatten a nested payload object into:
        - stable dotted keys
        - flat numeric vector

        Supported values:
        - int / float / bool
        - nested dicts
        - lists / tuples of numeric values
        """
        keys: list[str] = []
        vector: list[float] = []

        def visit(prefix: str, value: Any) -> None:
            if isinstance(value, dict):
                for key in sorted(value.keys()):
                    next_prefix = f"{prefix}.{key}" if prefix else str(key)
                    visit(next_prefix, value[key])
                return

            if isinstance(value, (list, tuple)):
                for idx, item in enumerate(value):
                    next_prefix = f"{prefix}[{idx}]"
                    visit(next_prefix, item)
                return

            if isinstance(value, bool):
                keys.append(prefix)
                vector.append(float(value))
                return

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric = float(value)
                if math.isnan(numeric) or math.isinf(numeric):
                    raise UpdateValidationError(f"Non-finite numeric value in payload at {prefix}")
                keys.append(prefix)
                vector.append(numeric)
                return

            raise UpdateValidationError(
                f"Unsupported payload value at {prefix or '<root>'}: {type(value).__name__}"
            )

        visit("", payload)
        return keys, vector

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

        if not isinstance(value, str) or not value.strip():
            raise UpdateValidationError("timestamp must be a non-empty string or datetime")

        normalized = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise UpdateValidationError(f"Invalid timestamp: {value}") from exc

        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @staticmethod
    def _require_payload_dict(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise UpdateValidationError("payload must be an object")
        return value

    @staticmethod
    def _safe_mean(values: Iterable[float]) -> float:
        vals = list(values)
        return sum(vals) / len(vals) if vals else 0.0


# Module-level singleton used by the rest of the backend.
aggregator_service = AggregatorService()
