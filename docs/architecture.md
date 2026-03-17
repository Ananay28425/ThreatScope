# ThreatScope — Architecture Documentation

## System Overview

ThreatScope is a distributed, privacy-preserving cyber threat intelligence platform. The core design principle is **signal sharing without data sharing**: each participating organization runs local anomaly detection on its private logs and shares only derived, irreversible signals with the central orchestrator.

---

## Privacy Model

### What is NEVER shared

- Raw log entries (IP addresses, usernames, request payloads, timestamps of individual events)
- Network topology or infrastructure details
- User identities or session data

### What IS shared (signals)

| Signal Type | Example | Why it's safe |
|---|---|---|
| Statistical aggregate | `{ "failed_login_rate": 0.42, "ip_entropy": 3.7 }` | No individual identifiable |
| Anomaly score | `{ "anomaly_score": 0.87 }` | Single float — irreversible |
| Behavioral fingerprint | `{ "fingerprint": "AUTH_FAIL_BURST" }` | Pattern label, no raw data |
| Confidence metadata | `{ "confidence": 0.91, "window_seconds": 60 }` | Model quality indicator |

**Privacy guarantee**: even if all signals from a node were intercepted, it is mathematically impossible to reconstruct the raw logs they were derived from.

---

## Component Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        PRIVACY BOUNDARY                              │
│                                                                      │
│  ┌─────────────┐   ┌─────────────────────┐   ┌────────────────────┐ │
│  │   Node A    │   │       Node B        │   │       Node C       │ │
│  │             │   │                     │   │                    │ │
│  │ Private     │   │ Private Logs        │   │ Private Logs       │ │
│  │ Logs        │   │ (never leave)       │   │ (never leave)      │ │
│  │      │      │   │        │            │   │        │           │ │
│  │ Feature     │   │ Feature Extraction  │   │ Feature Extraction │ │
│  │ Extraction  │   │ (windowed stats)    │   │ (windowed stats)   │ │
│  │      │      │   │        │            │   │        │           │ │
│  │ Isolation   │   │ Isolation Forest    │   │ Isolation Forest   │ │
│  │ Forest +    │   │ + Rules             │   │ + Rules            │ │
│  │ Rules       │   │        │            │   │        │           │ │
│  └──────┬──────┘   └────────┬────────────┘   └────────┬───────────┘ │
│         │                   │                         │             │
└─────────┼───────────────────┼─────────────────────────┼─────────────┘
          │  SIGNALS ONLY     │                         │
          └───────────────────┴─────────────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │   Valkey Stream    │
                    │  (signal topic)    │
                    └─────────┬──────────┘
                              │
                    ┌─────────▼──────────┐
                    │  FastAPI           │
                    │  Orchestrator      │
                    │                   │
                    │  ┌─────────────┐  │
                    │  │ Correlation │  │
                    │  │   Engine    │  │
                    │  └──────┬──────┘  │
                    └─────────┼──────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼──────┐  ┌────▼────┐  ┌───────▼────────┐
    │   PostgreSQL   │  │Prometheus│  │   WebSocket    │
    │   (alerts,     │  │(metrics) │  │   (push to     │
    │    metadata)   │  └────┬────┘  │    dashboard)  │
    └────────────────┘       │       └───────┬────────┘
                        ┌────▼────┐          │
                        │ Grafana │  ┌───────▼────────┐
                        │dashboards│  │ React + Three.js│
                        └─────────┘  │ 3D SOC Globe   │
                                     └────────────────┘
```

---

## Correlation Engine

The central intelligence of ThreatScope. Replaces full federated ML training with a simpler, more reliable sliding-window rule-based system.

### Algorithm

```
FOR each incoming signal:
  1. Add to buffer[fingerprint]
  2. Prune records older than WINDOW (default: 120s)
  3. Filter buffer to records with anomaly_score ≥ THRESHOLD (default: 0.80)
  4. Count distinct contributing node IDs
  5. IF distinct_nodes ≥ MIN_NODES (default: 3):
       - Compute confidence-weighted mean score
       - Classify severity (MEDIUM / HIGH / CRITICAL)
       - Create alert record
       - Broadcast via WebSocket to all connected SOC clients
```

### Severity Classification

| Condition | Severity |
|---|---|
| score ≥ 0.95 OR nodes ≥ 8 | CRITICAL |
| score ≥ 0.90 OR nodes ≥ 6 | HIGH |
| score ≥ 0.80 OR nodes ≥ 3 | MEDIUM |

### Why this beats full federated training

For a 3-month project timeline:
- Full federated training requires: gradient aggregation, model versioning, poisoning defenses, per-node training pipelines
- Rule-based correlation delivers: sub-millisecond decisions, zero training overhead, fully debuggable, no model drift

In real industry SOC tools (e.g., Splunk ES, Elastic SIEM), rule-based correlation is the primary detection mechanism. ML is additive, not foundational.

---

## Data Flow: Signal Lifecycle

```
1. Node generates 1000 raw events over 60 seconds
2. Feature extractor computes 7 aggregate statistics
3. Local detector (Isolation Forest + rules) produces anomaly_score ∈ [0,1]
4. signal_sender.py POSTs JSON signal to /api/signals/ingest
5. FastAPI validates with Pydantic strict mode (rejects raw log fields)
6. Signal fed to CorrelationEngine.ingest()
7. Engine evaluates: enough nodes? score threshold met?
8. If YES → Alert created → WebSocket broadcast → 3D globe flashes
9. Alert stored in PostgreSQL for audit trail
```

---

## WebSocket Event Contract

All events pushed from backend to frontend follow this schema:

```json
{
  "event_type": "new_alert | signal_pulse | node_status | metrics | connected",
  "payload": { ... },
  "timestamp": "2026-03-21T10:00:00Z"
}
```

### new_alert payload
```json
{
  "fingerprint": "AUTH_FAIL_BURST",
  "severity": "HIGH",
  "contributing_nodes": ["org_1", "org_3", "org_7"],
  "anomaly_score": 0.913,
  "node_count": 3
}
```

### signal_pulse payload
```json
{
  "node_id": "org_3",
  "timestamp": "2026-03-21T10:00:05Z",
  "anomaly_score": 0.84,
  "fingerprint": "AUTH_FAIL_BURST"
}
```

---

## Prometheus Metrics

| Metric | Type | Description |
|---|---|---|
| `threatscope_signals_ingested_total` | Counter | Total signals received, labelled by node + fingerprint |
| `threatscope_alerts_raised_total` | Counter | Alerts fired, labelled by severity + fingerprint |
| `threatscope_correlation_latency_seconds` | Histogram | Engine evaluation time (target: p99 < 10ms) |
| `threatscope_active_nodes` | Gauge | Currently live nodes |
| `threatscope_websocket_connections_active` | Gauge | Connected SOC analysts |

---

## Technology Decisions

### Valkey instead of Redis
Redis changed its license to SSPL (non-FOSS) in March 2024. Valkey is a BSD-3-Clause fork of Redis 7.2.4, maintained by the Linux Foundation. It is 100% RESP-protocol-compatible — `redis-py` connects without modification. Using Valkey means zero licensing cost and no vendor lock-in.

### FastAPI over Django
Django is a batteries-included framework optimized for database-heavy web apps. ThreatScope's backend is an async, streaming, event-driven service — FastAPI's async-native design and native WebSocket support are a better fit. Django REST Framework adds overhead without benefit here.

### Isolation Forest for local detection
Unsupervised, requires no labelled training data (critical for a simulation), handles high-dimensional feature vectors, and is computationally cheap enough to run per-node at 60-second intervals. One-Class SVM is an alternative but scales poorly with dataset size.

### Rule-based correlation over federated ML
See "Why this beats full federated training" above. The rule-based engine is faster, more debuggable, and delivers the same observable outcome for the demo.
