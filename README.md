# ThreatScope

Privacy-preserving, real-time cyber threat intelligence platform for correlating distributed attack signals without sharing raw logs.

---

## Overview

ThreatScope is designed for environments where multiple organizations or nodes want to collaborate on threat detection without exposing sensitive telemetry. Each node performs local analysis, extracts privacy-safe features, and sends only sanitized signals to a central backend. The backend correlates those signals, raises alerts, and streams live updates to a SOC dashboard.

The repository includes:

- a `FastAPI` backend
- a `React + Vite` frontend
- a `node_simulator` for generating synthetic threat signals
- observability infrastructure with `Prometheus` and `Grafana`
- test scaffolding for unit and load testing
- deployment and architecture documentation

---

## Repository Structure

```text
threatscope/
├─ README.md
├─ Makefile
├─ docker-compose.yml
├─ .env.example
├─ infra/
│  ├─ docker-compose.yml
│  ├─ grafana/
│  │  └─ dashboards/
│  └─ prometheus/
│     └─ prometheus.yml
├─ backend/
│  ├─ main.py
│  ├─ app/
│  │  ├─ api/
│  │  │  ├─ signals.py
│  │  │  ├─ alerts.py
│  │  │  └─ auth.py
│  │  ├─ services/
│  │  │  ├─ kafka_consumer.py
│  │  │  ├─ correlator.py
│  │  │  └─ aggregator.py
│  │  ├─ models/
│  │  └─ schemas/
│  ├─ requirements.txt
│  └─ Dockerfile
├─ node_simulator/
│  ├─ log_generator.py
│  ├─ feature_extractor.py
│  ├─ detector.py
│  ├─ signal_sender.py
│  ├─ models/
│  │  └─ sample_isolation.joblib
│  └─ Dockerfile
├─ models/
│  └─ distilled_model.joblib
├─ frontend/
│  ├─ package.json
│  ├─ vite.config.js
│  ├─ src/
│  │  ├─ App.jsx
│  │  ├─ api/
│  │  │  └─ websocket.js
│  │  ├─ store/
│  │  │  └─ useStore.js
│  │  ├─ components/
│  │  │  ├─ Dashboard.jsx
│  │  │  ├─ AlertsPanel.jsx
│  │  │  └─ ThreatMap.jsx
│  │  └─ styles/
│  └─ Dockerfile
├─ tests/
│  ├─ unit/
│  │  ├─ test_correlator.py
│  │  └─ test_signal_sender_no_raw.py
│  └─ load/
│     └─ locustfile.py
└─ docs/
   ├─ topics.md
   └─ deployment.md
```

---

## Architecture Summary

### 1. Node-side detection

Each simulated organization runs a local pipeline:

- `log_generator.py` creates synthetic traffic and security events
- `feature_extractor.py` computes windowed, privacy-safe features such as:
  - request rate
  - failed login rate
  - unique IP count
  - entropy-based indicators
  - response/error metrics
- `detector.py` applies local anomaly detection
- `signal_sender.py` sends only sanitized signals onward

No raw logs should leave the node boundary.

### 2. Central backend

The backend is responsible for:

- accepting signal ingestion requests
- authenticating nodes and dashboard users
- correlating signals across multiple nodes
- aggregating model update metadata
- exposing alert APIs
- streaming events to the frontend
- preparing for Kafka-driven ingestion and alert workflows

Core backend areas:

- `backend/app/api/`
  - REST endpoints
- `backend/app/services/`
  - correlation, ingestion, and aggregation logic
- `backend/app/models/`
  - ORM/data models
- `backend/app/schemas/`
  - request/response validation models

### 3. Frontend SOC dashboard

The frontend provides a live operational view with:

- dashboard overview panels
- real-time alerts
- threat map visualization
- centralized client-side state
- WebSocket-based live updates

### 4. Observability

The repository includes observability support through:

- `Prometheus` for metrics scraping
- `Grafana` for dashboards
- infrastructure compose files for local stack orchestration

---

## Core Data Flow

1. A node generates local events.
2. The node extracts privacy-safe aggregate features.
3. A local detector produces anomaly scores and fingerprints.
4. The node sends a sanitized signal to the backend or stream layer.
5. The backend validates and correlates the signal.
6. If a distributed pattern is detected, the backend raises an alert.
7. The frontend receives updates over WebSocket and renders them live.
8. Metrics are exported for Prometheus and visualized in Grafana.

---

## Main Components

## Backend

Path: `backend/`

Key files:

- `main.py`  
  FastAPI application entrypoint

- `app/api/signals.py`  
  signal ingestion endpoints and validation flow

- `app/api/alerts.py`  
  alert listing and incident management endpoints

- `app/api/auth.py`  
  API-key and dashboard auth stubs

- `app/services/kafka_consumer.py`  
  consumer logic for `node_signals` and `model_updates`

- `app/services/correlator.py`  
  central correlation logic and alert shaping

- `app/services/aggregator.py`  
  update aggregation strategies such as FedAvg or robust summaries

## Node Simulator

Path: `node_simulator/`

Key files:

- `log_generator.py`
- `feature_extractor.py`
- `detector.py`
- `signal_sender.py`

These files simulate the org-side agent boundary and are central to the privacy-preserving design.

## Frontend

Path: `frontend/`

Key files:

- `src/App.jsx`
- `src/api/websocket.js`
- `src/store/useStore.js`
- `src/components/Dashboard.jsx`
- `src/components/AlertsPanel.jsx`
- `src/components/ThreatMap.jsx`

## Infrastructure

Path: `infra/`

Includes:

- `docker-compose.yml`
- `prometheus/prometheus.yml`
- `grafana/dashboards/`

## Tests

Path: `tests/`

Includes:

- `tests/unit/test_correlator.py`
- `tests/unit/test_signal_sender_no_raw.py`
- `tests/load/locustfile.py`

## Documentation

Path: `docs/`

Includes:

- `topics.md`
- `deployment.md`

---

## Local Development

### Prerequisites

Recommended local versions:

- Python 3.11+
- Node.js 20+
- Docker + Docker Compose
- Make

### Environment

Copy the example environment file and adjust values as needed:

```bash
cp .env.example .env
```

You may also need a backend-specific environment file depending on how you run the backend locally.

---

## Running the Stack

### Option 1: Repo-root compose stack

```bash
docker compose up --build
```

### Option 2: Infra compose stack

```bash
docker compose -f infra/docker-compose.yml up --build
```

### Helpful Make targets

```bash
make up
make down
make logs
make backend
make frontend
make simulator
make test
```

---

## Expected Local Services

Typical local endpoints:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

Exact ports depend on your compose configuration.

---

## Testing

### Unit tests

```bash
pytest tests/unit -v
```

### Load tests

```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

---

## Privacy Model

ThreatScope is built around one key rule:

> Share signals, not raw data.

Allowed outbound artifacts include:

- anomaly scores
- statistical summaries
- behavioral fingerprints
- confidence values
- model metadata summaries

Disallowed outbound artifacts include:

- raw log lines
- usernames and passwords
- full payload bodies
- private infrastructure identifiers
- direct user-identifying data

The simulator and tests should enforce this principle.

---

## Kafka Topics and Contracts

Documented topic contracts live in:

- `docs/topics.md`

Primary topics:

- `node_signals`
- `model_updates`
- `alerts`

These contracts define the intended event-driven integration model even when local demos also use direct HTTP and WebSocket flows.

---

## Deployment Notes

Deployment and demo instructions live in:

- `docs/deployment.md`

This includes:

- environment setup
- compose-based startup
- hybrid local dev workflow
- demo flow suggestions
- troubleshooting guidance

---

## Current Intent of the Repository

This repository is structured to support:

- a privacy-preserving cyber threat intelligence demo
- local development with clear separation between frontend, backend, simulator, and infra
- future integration of streaming and aggregation workflows
- academic, prototype, and portfolio use cases

---

## Suggested Next Steps

If you are extending the project, the most useful next improvements are:

1. persist alerts and signals in the database
2. wire all API modules consistently into the backend app
3. connect Kafka consumers/producers end to end
4. replace auth stubs with production-ready auth flows
5. add deterministic model artifact generation scripts
6. expand unit and integration coverage
7. add CI validation for repo structure and docs consistency

---

## License

See `LICENSE`.
