# ThreatScope Deployment and Demo Guide

This document explains how to run ThreatScope locally for development, testing, and demo purposes using the repository layout in this project.

## Overview

ThreatScope is composed of:

- `backend/` — FastAPI orchestration service
- `frontend/` — React + Vite SOC dashboard
- `node_simulator/` — synthetic node agents that generate privacy-safe signals
- `infra/` — Prometheus, Grafana, and local stack container configuration
- `tests/` — unit and load tests
- `docs/` — architecture and operations notes

The standard local deployment includes:

- Backend API
- Frontend dashboard
- PostgreSQL
- Redis-compatible cache/message broker
- Prometheus
- Grafana
- Node simulator

## Prerequisites

Install the following before running the stack:

- Docker Desktop or Docker Engine with Compose support
- Python 3.11+
- Node.js 20+
- `make` or an equivalent shell environment if you want shortcut commands

Optional but useful:

- `curl`
- `pytest`
- `locust`

## Environment Setup

Create environment files before first run.

### Root example

Copy the repository example file:

```/dev/null/.env.example#L1-20
# Copy this file to .env for local development
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000

DATABASE_URL=postgresql+asyncpg://threatscope:threatscope@postgres:5432/threatscope
SYNC_DATABASE_URL=postgresql://threatscope:threatscope@postgres:5432/threatscope

REDIS_URL=redis://redis:6379/0
KAFKA_BOOTSTRAP_SERVERS=kafka:9092

JWT_SECRET_KEY=change-me
NODE_API_KEY=dev-node-key
GRAFANA_ADMIN_PASSWORD=admin
```

If the root `.env.example` does not yet exist in your checkout, create `.env` manually with values appropriate for local development.

### Backend environment

If your backend uses its own environment file, ensure it contains at least:

- application environment
- database URL
- broker/cache URL
- auth secret
- node API key

Recommended local values:

- app env: `development`
- backend port: `8000`
- frontend port: `5173`
- Grafana admin password: `admin`

## Local Deployment Options

You can run ThreatScope in two ways:

1. Fully containerized with Docker Compose
2. Hybrid local development with services in containers and app code run directly

---

## Option 1: Run the Full Stack with Docker Compose

From the repository root:

```/dev/null/commands.sh#L1-4
docker compose up --build
# or, if using infra compose explicitly
docker compose -f infra/docker-compose.yml up --build
```

Run in detached mode if preferred:

```/dev/null/commands.sh#L1-2
docker compose up --build -d
```

To stop:

```/dev/null/commands.sh#L1-2
docker compose down
```

To stop and remove volumes:

```/dev/null/commands.sh#L1-2
docker compose down -v
```

### Expected service endpoints

After startup, the typical endpoints are:

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger docs: `http://localhost:8000/docs`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`

If your compose file maps different ports, use those mapped host ports instead.

---

## Option 2: Run Services in Containers, Apps Locally

This mode is useful when developing backend or frontend interactively.

### Start infrastructure only

If your compose file supports selective service startup:

```/dev/null/commands.sh#L1-2
docker compose up -d postgres redis prometheus grafana
```

If the repository uses a different cache or broker service name, use that name from the compose file.

### Run backend locally

From `backend/`:

```/dev/null/commands.sh#L1-4
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python main.py
```

Or with Uvicorn directly:

```/dev/null/commands.sh#L1-2
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run frontend locally

From `frontend/`:

```/dev/null/commands.sh#L1-4
npm install
npm run dev
```

### Run node simulator locally

From `node_simulator/`:

```/dev/null/commands.sh#L1-4
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
python signal_sender.py --nodes 5 --interval 5
```

---

## Suggested Demo Flow

This section is optimized for classroom, review, or stakeholder demonstration.

### Demo goal

Show that:

1. nodes generate local events
2. only privacy-safe signals are sent centrally
3. backend correlates signals across nodes
4. frontend receives live updates
5. observability stack shows system health

### Step 1: Start the full stack

```/dev/null/demo.sh#L1-2
docker compose up --build
```

Wait until the backend and frontend are reachable.

### Step 2: Open the main interfaces

Open these in the browser:

- `http://localhost:5173`
- `http://localhost:8000/docs`
- `http://localhost:3000`
- `http://localhost:9090`

### Step 3: Start node activity

If node simulator is not already part of Compose, start it manually:

```/dev/null/demo.sh#L1-2
python node_simulator/signal_sender.py --nodes 5 --interval 2
```

This should begin generating live signals.

### Step 4: Verify ingestion

Use the API docs or a quick health request:

```/dev/null/demo.sh#L1-2
curl http://localhost:8000/health
```

You should receive an `ok` style response.

### Step 5: Watch the frontend

In the dashboard, show:

- live alerts panel
- node activity updates
- threat visualization
- WebSocket-driven UI changes

### Step 6: Show Prometheus and Grafana

In Prometheus:

- inspect backend metrics
- verify alert/signal counters

In Grafana:

- open the prebuilt dashboard
- show alert throughput, node counts, and service health

---

## Backend Startup Notes

The backend is expected to provide:

- REST API routes under `/api`
- WebSocket endpoint for live threat stream
- `/health`
- `/metrics`

Typical checks:

```/dev/null/commands.sh#L1-3
curl http://localhost:8000/health
curl http://localhost:8000/metrics
curl http://localhost:8000/docs
```

If authentication is enabled for some routes, use the configured development credentials or API key.

## Frontend Startup Notes

The frontend expects:

- backend API base URL
- backend WebSocket URL

Typical Vite environment values:

```/dev/null/frontend.env#L1-4
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
VITE_APP_NAME=ThreatScope
```

If using Docker, ensure the frontend receives the correct hostnames for container-to-container communication and browser-accessible URLs.

## Node Simulator Notes

The simulator should never send raw logs to the backend. It should only send aggregated or sanitized signals such as:

- anomaly score
- confidence
- fingerprint
- window metrics

Example run commands:

```/dev/null/node-demo.sh#L1-3
python signal_sender.py --node-id org_1 --interval 5
python signal_sender.py --nodes 3 --interval 2
python signal_sender.py --nodes 10 --interval 1
```

For a deterministic demo, keep:

- fixed node count
- small interval
- stable backend URL
- known API key

## Makefile Suggestions

If a `Makefile` exists or is added later, these are the recommended targets:

```/dev/null/Makefile#L1-18
up:
	docker compose up --build

down:
	docker compose down

demo:
	python node_simulator/signal_sender.py --nodes 5 --interval 2

backend:
	cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test:
	pytest tests/unit -v

load:
	locust -f tests/load/locustfile.py --host=http://localhost:8000
```

## Running Unit Tests

From the repository root:

```/dev/null/test.sh#L1-2
pytest tests/unit -v
```

If backend imports require the backend directory on the Python path:

```/dev/null/test.sh#L1-2
PYTHONPATH=backend pytest tests/unit -v
```

On Windows PowerShell:

```/dev/null/test.ps1#L1-2
$env:PYTHONPATH="backend"
pytest tests/unit -v
```

## Running Load Tests

From the repository root:

```/dev/null/load.sh#L1-2
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

Then open the Locust UI in the browser, usually at:

- `http://localhost:8089`

Recommended demo settings:

- users: `20`
- spawn rate: `5`
- duration: `2m`

Use a higher load only if your machine has enough memory and CPU.

## Troubleshooting

### Backend does not start

Check for:

- missing environment variables
- database not reachable
- broker/cache not reachable
- port `8000` already in use

Useful checks:

```/dev/null/troubleshoot.sh#L1-4
docker compose ps
docker compose logs backend
docker compose logs postgres
docker compose logs redis
```

If your project uses a different service name than `redis`, inspect the compose services and substitute the correct one.

### Frontend cannot connect to backend

Symptoms:

- blank dashboard
- failed API requests
- WebSocket disconnect loops

Verify:

- `VITE_API_URL`
- `VITE_WS_URL`
- backend CORS configuration
- backend port mapping

### Grafana shows no data

Check:

- Prometheus is running
- backend exposes `/metrics`
- Prometheus scrape config points to the correct backend target
- Grafana datasource points to Prometheus

### Database errors

If schema initialization is missing, ensure migrations or table creation steps have run before using alert endpoints.

### Node simulator cannot ingest

Check:

- backend URL
- API key header or configured auth
- route path for signal ingestion
- network path between simulator and backend

---

## Production-Oriented Notes

This repository is intended primarily for local demo and academic deployment, but if you extend it toward production, consider:

- replacing development secrets
- using managed PostgreSQL
- using TLS for all HTTP and WebSocket traffic
- placing backend behind a reverse proxy
- externalizing Grafana and Prometheus storage
- adding structured log shipping
- introducing Kafka or a durable queue if required by the architecture version you adopt
- adding CI/CD and image version pinning
- implementing DB migrations and backup policies

## Minimal Demo Checklist

Use this checklist before presenting:

- [ ] `.env` configured
- [ ] containers build successfully
- [ ] backend reachable at `/health`
- [ ] frontend loads in browser
- [ ] WebSocket connection established
- [ ] simulator sending signals
- [ ] alerts visible in dashboard
- [ ] Prometheus scraping metrics
- [ ] Grafana dashboard loads
- [ ] unit tests pass

## Quick Start Summary

For the fastest local demo:

```/dev/null/quickstart.sh#L1-5
docker compose up --build -d
python node_simulator/signal_sender.py --nodes 5 --interval 2
curl http://localhost:8000/health
pytest tests/unit -v
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

Once the stack is up, open the frontend and observability tools and walk through the live signal-to-alert pipeline.
