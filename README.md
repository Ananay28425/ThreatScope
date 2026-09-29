# ThreatScope

ThreatScope is a research prototype for policy-controlled security evidence sharing, deterministic correlation, and local explanations. Organization agents keep raw events local, release a finite catalogue of derived values, and retain a durable release ledger. A PostgreSQL coordinator records signals before acknowledging them. Independent workers correlate evidence and prepare recipient-scoped explanations.

**A supported rule is not proof of compromise.** Derived values still reveal activity patterns. Release costs are policy units, not differential-privacy guarantees. Current experiments use labeled synthetic organization partitions; they do not establish production scalability or publication novelty.

## Start the three-organization demo

Requirements: Docker Compose v2, Python 3.12 for bootstrap, and sufficient disk space for images. Native PostgreSQL execution is also supported in [deployment instructions](docs/deployment.md).

```sh
python scripts/bootstrap.py
docker compose build
docker compose up -d --wait backend correlation explanations frontend
docker compose --profile setup run --rm enroll
docker compose --profile demo up -d orion lyra vega
```

Open <http://127.0.0.1:5173>. Read the generated administrator login from `.runtime/private/demo-credentials.json` locally. Do not commit, paste, or distribute this file. Each agent mounts only its own node credential file and owns a separate SQLite volume. The database has no published host port. Enrollment refuses an already enrolled database; do not rerun it to reset passwords.

Local inference is optional during setup. The default explanation path uses a deterministic fallback until the local endpoint is configured. The [model setup script](scripts/setup_models.py) downloads pinned official weights and llama.cpp. Qwen3-1.7B Q4_K_M is derived by requantizing official Q8_0 weights; that distinction is recorded in `research/models.lock.json`. Qwen3-4B Q4_K_M is the larger comparison configuration. There is no cloud fallback.

## Develop and verify

```sh
uv sync --frozen
uv run pytest -q
uv run ruff check backend common node_simulator migrations scripts tests research
cd frontend
npm ci
npm run lint
npm run build
```

Set `TEST_DATABASE_URL` to an isolated PostgreSQL test database to run the same API tests with PostgreSQL concurrency semantics. Each test creates and removes its own random schema. Never point the test setting at a production database. CI checks SQLite, PostgreSQL, the frontend, and a Compose smoke run.

## Read the implementation

- [Architecture and limits](docs/architecture.md): trust boundaries, state ownership, failure modes, and budgets.
- [Deployment and recovery](docs/deployment.md): native services, migrations, backup, restore, and inference connectivity.
- [Versioned contracts](docs/contracts.md): ingestion, evidence, sessions, events, and explanations.
- `research/`: frozen cases, source metadata, evaluation programs, and measured outputs.
- `tests/`: behavioral tests covering authorization, replay, disclosure budgets, and explanation support.

Legacy Kafka, ZooKeeper, Redis, Celery, competing API routes, and token-in-browser storage have been removed. Existing database tables are preserved by the new migration and copied into a quarantined legacy archive. They are not treated as authenticated research evidence. There is one root Compose definition and one Python dependency lock.

No automated conference submission, payment, patent filing, public release, or main-branch merge is part of this repository update.
