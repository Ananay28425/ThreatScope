# ThreatScope Kafka Topics and Message Schemas

This document defines the event topics used by ThreatScope, their intended producers and consumers, and the canonical JSON message shapes exchanged between system components.

> Note: the current codebase may use HTTP ingestion and WebSocket streaming for parts of the demo flow. These topic contracts document the intended event-driven architecture and should be treated as the source of truth for Kafka-based integration.

---

## Topic Overview

| Topic | Produced By | Consumed By | Purpose |
|---|---|---|---|
| `node_signals` | Node agents / simulator | Backend correlation pipeline | Privacy-safe anomaly signals from participating organizations |
| `model_updates` | Node agents | Backend aggregation service | Local model summaries or parameter updates for centralized aggregation |
| `alerts` | Backend correlator | Frontend gateways, notification workers, analytics services | Global alerts raised after cross-node correlation |

---

## Design Principles

1. **No raw logs in Kafka**
   - Topics must never contain raw log lines, usernames, passwords, request payloads, or full IP addresses from private infrastructure.
   - Only sanitized, aggregated, and privacy-safe features are allowed.

2. **JSON-encoded messages**
   - All messages are UTF-8 JSON objects.
   - Producers should include all required fields.
   - Consumers should ignore unknown optional fields for forward compatibility.

3. **Schema evolution**
   - Additive changes are preferred.
   - Removing or renaming fields should be avoided unless topic versioning is introduced.

4. **Timestamps**
   - All timestamps must be ISO 8601 / RFC 3339 in UTC.
   - Example: `2026-03-21T10:00:05Z`

5. **Keys and partitioning**
   - `node_signals`: key by `node_id`
   - `model_updates`: key by `node_id`
   - `alerts`: key by `alert_id` or `fingerprint`

---

## Topic: `node_signals`

### Purpose

Carries privacy-preserving anomaly signals from each node to the central backend. This is the most important operational topic in the system.

### Producers

- `node_simulator/signal_sender.py`
- Future real organization-side node agents

### Consumers

- `backend/app/services/kafka_consumer.py`
- `backend/app/services/correlator.py`
- Optional metrics and archival processors

### Delivery Expectations

- At-least-once delivery is acceptable
- Consumers should be idempotent where possible
- Duplicate messages may occur and must not cause duplicate node counting inside the correlation window

### Required Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `signal_id` | string | yes | Unique signal identifier |
| `node_id` | string | yes | Sanitized node/org identifier |
| `timestamp` | string | yes | UTC event timestamp |
| `anomaly_score` | number | yes | Float in range `0.0` to `1.0` |
| `confidence` | number | yes | Float in range `0.0` to `1.0` |
| `fingerprint` | string or null | yes | Behavioral pattern label such as `AUTH_FAIL_BURST` |
| `window_seconds` | integer | yes | Aggregation window size |
| `metrics` | object | yes | Privacy-safe aggregated metrics |
| `schema_version` | string | yes | Topic schema version, e.g. `1.0` |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `org_region` | string | Approximate geographic region like `eu-west` or `us-east` |
| `model_version` | string | Local detector version |
| `transport` | string | Ingestion mode like `kafka` or `http-bridge` |

### JSON Schema Shape

```ThreatScope/docs/topics.md#L67-93
{
  "signal_id": "sig_01HZX2QK1Z7M7K8P4YJ9W2A1BC",
  "node_id": "org_3",
  "timestamp": "2026-03-21T10:00:05Z",
  "anomaly_score": 0.913,
  "confidence": 0.97,
  "fingerprint": "AUTH_FAIL_BURST",
  "window_seconds": 60,
  "metrics": {
    "request_rate": 142.3,
    "failed_login_rate": 0.61,
    "unique_ip_count": 483,
    "ip_entropy": 4.82,
    "error_rate_4xx": 0.28,
    "error_rate_5xx": 0.04,
    "avg_response_time_ms": 287.5
  },
  "schema_version": "1.0",
  "org_region": "eu-west",
  "model_version": "isolation_forest_v1",
  "transport": "kafka"
}
```

### Validation Rules

- `anomaly_score` must be between `0.0` and `1.0`
- `confidence` must be between `0.0` and `1.0`
- `window_seconds` should normally be between `10` and `600`
- `metrics` must only contain aggregated numeric values
- Blocked raw-field names include:
  - `user_id`
  - `username`
  - `password`
  - `payload`
  - `ip`
  - `ip_address`
  - `email`
  - `session_id`

### Privacy Constraints

The following are explicitly forbidden in `node_signals`:

- Raw log lines
- Full request bodies
- Authentication credentials
- Session cookies
- Private internal hostnames
- Packet captures
- Directly identifying user data

---

## Topic: `model_updates`

### Purpose

Carries local model update metadata from nodes to the backend aggregation service. This supports future centralized aggregation workflows such as FedAvg, weighted blending, or robust aggregation.

### Producers

- Node agents after local training or recalibration

### Consumers

- `backend/app/services/kafka_consumer.py`
- `backend/app/services/aggregator.py`

### Notes

For the current demo, this can be a lightweight metadata topic rather than a full tensor/gradient stream. If true federated learning is introduced later, payload size and serialization format may need to change.

### Required Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `update_id` | string | yes | Unique model update identifier |
| `node_id` | string | yes | Origin node identifier |
| `timestamp` | string | yes | UTC timestamp of update creation |
| `model_version` | string | yes | Version of the local model |
| `aggregation_round` | integer | yes | Federated aggregation round number |
| `sample_count` | integer | yes | Number of local windows/examples used |
| `update_type` | string | yes | Type such as `fedavg`, `summary`, `robust` |
| `payload` | object | yes | Numeric update payload or model summary |
| `schema_version` | string | yes | Topic schema version |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `quality_score` | number | Local confidence in the update quality |
| `training_duration_ms` | integer | Approximate local training time |
| `node_weight` | number | Relative weighting hint for aggregation |

### JSON Schema Shape

```ThreatScope/docs/topics.md#L142-163
{
  "update_id": "upd_01HZX31J4PRB4JYJ91Y2R5XJ20",
  "node_id": "org_7",
  "timestamp": "2026-03-21T10:05:00Z",
  "model_version": "isolation_forest_v2",
  "aggregation_round": 4,
  "sample_count": 1250,
  "update_type": "summary",
  "payload": {
    "feature_means": [81.2, 0.08, 141.0, 2.94, 0.03, 0.01, 118.7],
    "feature_stds": [12.5, 0.04, 31.7, 0.62, 0.02, 0.01, 21.3],
    "contamination": 0.05
  },
  "quality_score": 0.93,
  "training_duration_ms": 842,
  "node_weight": 1.0,
  "schema_version": "1.0"
}
```

### Validation Rules

- `aggregation_round` must be non-negative
- `sample_count` must be positive
- `payload` should remain numeric and compact
- Large binary blobs should not be sent in this topic unless the architecture is explicitly updated

### Recommended Aggregation Strategies

- **FedAvg** for simple weighted averaging
- **Median / trimmed mean** for robustness
- **Quality-weighted blending** using `sample_count` and `quality_score`

---

## Topic: `alerts`

### Purpose

Broadcasts globally correlated alerts created by the backend after enough nodes report related anomalous behavior.

### Producers

- `backend/app/services/correlator.py`
- Backend incident pipeline

### Consumers

- Frontend alert bridge / WebSocket broadcaster
- Notification workers
- Incident management integrations
- Analytics and audit sinks

### Required Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `alert_id` | string | yes | Unique alert identifier |
| `timestamp` | string | yes | UTC creation timestamp |
| `severity` | string | yes | `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL` |
| `fingerprint` | string or null | yes | Correlated attack pattern |
| `anomaly_score` | number | yes | Weighted aggregate score |
| `node_count` | integer | yes | Number of contributing distinct nodes |
| `contributing_nodes` | array of string | yes | List of node IDs that contributed |
| `status` | string | yes | Alert lifecycle state |
| `description` | string | yes | Human-readable summary |
| `schema_version` | string | yes | Topic schema version |

### Optional Fields

| Field | Type | Description |
|---|---|---|
| `recommended_action` | string | Analyst guidance |
| `mitre_attack` | array of string | ATT&CK technique IDs |
| `regions` | array of string | Regions where affected nodes are located |
| `correlation_window_seconds` | integer | Window used to produce the alert |

### JSON Schema Shape

```ThreatScope/docs/topics.md#L218-240
{
  "alert_id": "alt_01HZX38G7MZ4T4A1R3Q8N0HB9D",
  "timestamp": "2026-03-21T10:05:15Z",
  "severity": "HIGH",
  "fingerprint": "AUTH_FAIL_BURST",
  "anomaly_score": 0.914,
  "node_count": 4,
  "contributing_nodes": ["org_1", "org_3", "org_7", "org_9"],
  "status": "open",
  "description": "Distributed authentication failure burst detected across 4 nodes within 120 seconds.",
  "recommended_action": "Investigate credential stuffing indicators and rate-limit affected login endpoints.",
  "mitre_attack": ["T1110"],
  "regions": ["eu-west", "us-east"],
  "correlation_window_seconds": 120,
  "schema_version": "1.0"
}
```

### Severity Guidance

| Condition | Severity |
|---|---|
| score `< 0.80` and limited spread | `LOW` |
| score `>= 0.80` or `>= 3` nodes | `MEDIUM` |
| score `>= 0.90` or `>= 6` nodes | `HIGH` |
| score `>= 0.95` or `>= 8` nodes | `CRITICAL` |

### Status Values

- `open`
- `investigating`
- `resolved`

---

## Suggested Kafka Configuration

These are reasonable defaults for a local or demo deployment.

### `node_signals`
- Partitions: `6`
- Replication factor: `1` for local demo, `3` for production
- Retention: `3d`
- Cleanup policy: `delete`

### `model_updates`
- Partitions: `3`
- Replication factor: `1` for local demo, `3` for production
- Retention: `7d`
- Cleanup policy: `delete`

### `alerts`
- Partitions: `3`
- Replication factor: `1` for local demo, `3` for production
- Retention: `14d`
- Cleanup policy: `delete`

---

## Consumer Group Recommendations

| Consumer | Group ID |
|---|---|
| Correlation pipeline | `threatscope-correlator` |
| Aggregation service | `threatscope-aggregator` |
| Alert broadcaster | `threatscope-alert-broadcaster` |
| Audit sink | `threatscope-audit` |

---

## Error Handling and Dead-Letter Strategy

If a consumer cannot parse or validate a message:

1. Log the schema failure with message metadata
2. Do not crash the entire consumer loop
3. Send the original payload to a dead-letter topic if enabled

Suggested DLQ topics:

- `node_signals_dlq`
- `model_updates_dlq`
- `alerts_dlq`

DLQ messages should include:

- `original_topic`
- `error`
- `failed_at`
- `raw_payload`

---

## Compatibility Notes

Although this document standardizes on Kafka topics, the current project may still use:

- HTTP for node signal ingestion
- WebSockets for frontend alert delivery
- Valkey-compatible infrastructure in local demos

That is fine. The schemas in this file are still useful because they define the canonical event contracts that backend services, simulators, and future Kafka consumers should follow.

---

## Minimal Examples

### Minimal `node_signals` message

```ThreatScope/docs/topics.md#L306-317
{
  "signal_id": "sig_demo_1",
  "node_id": "org_1",
  "timestamp": "2026-03-21T10:00:00Z",
  "anomaly_score": 0.84,
  "confidence": 0.91,
  "fingerprint": "TRAFFIC_SPIKE",
  "window_seconds": 60,
  "metrics": {
    "request_rate": 510.0
  },
  "schema_version": "1.0"
}
```

### Minimal `model_updates` message

```ThreatScope/docs/topics.md#L321-331
{
  "update_id": "upd_demo_1",
  "node_id": "org_1",
  "timestamp": "2026-03-21T10:02:00Z",
  "model_version": "iforest_v1",
  "aggregation_round": 1,
  "sample_count": 500,
  "update_type": "summary",
  "payload": {
    "contamination": 0.05
  },
  "schema_version": "1.0"
}
```

### Minimal `alerts` message

```ThreatScope/docs/topics.md#L335-346
{
  "alert_id": "alt_demo_1",
  "timestamp": "2026-03-21T10:03:00Z",
  "severity": "MEDIUM",
  "fingerprint": "TRAFFIC_SPIKE",
  "anomaly_score": 0.85,
  "node_count": 3,
  "contributing_nodes": ["org_1", "org_2", "org_3"],
  "status": "open",
  "description": "Correlated traffic spike detected across 3 nodes.",
  "schema_version": "1.0"
}
```
