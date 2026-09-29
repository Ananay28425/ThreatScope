# Deployment and recovery

## Reproducible setup

Use root `docker-compose.yml`, `uv.lock`, and `frontend/package-lock.json`. The Compose database is internal, and API/frontend ports bind to loopback. `python scripts/bootstrap.py` creates private settings and refuses replacement. Build, start services, enroll once, then start the optional `demo` profile as shown in the README. Do not use `down -v` to restart: it deletes database and agent volumes.

The base deployment uses deterministic explanations until an inference endpoint is configured. The dashboard reports whether inference is configured; configuration alone does not establish service health. A failed generation returns a labeled fallback. Optional external monitoring can poll the authenticated `/api/v1/status` endpoint for queue depth and oldest pending age, and `/health/live` and `/health/ready` for process/database checks. Old dashboards with unsupported metrics were removed.

## Native PostgreSQL alternative

Install PostgreSQL 16 and create a dedicated database and restricted service role. Set `DATABASE_URL` to its SQLAlchemy `postgresql+asyncpg` URL, install `uv sync --frozen`, then run:

```sh
uv run alembic upgrade head
uv run python -m backend.app.admin seed-demo --output .runtime/private/demo-credentials.json
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In separate terminals using the same database configuration:

```sh
uv run python -m backend.app.worker
uv run python -m backend.app.explain_worker
uv run python -m node_simulator.agent --credentials .runtime/private/orion-node.json --state .runtime/orion.db --seed 41
uv run python -m node_simulator.agent --credentials .runtime/private/lyra-node.json --state .runtime/lyra.db --seed 42
uv run python -m node_simulator.agent --credentials .runtime/private/vega-node.json --state .runtime/vega.db --seed 43
```

Run `npm ci` and `npm run dev` in `frontend`. Its same-origin development proxy defaults to port 8000; set `BACKEND_URL` before starting Vite when using another port. Native browser origins must match `ALLOWED_ORIGINS`. The task's verification instance uses ports 18000 (API), 18080 (inference), 55432 (isolated PostgreSQL), and 5173 (dashboard).

For Windows without an available Docker engine, `scripts/local_runtime.py` initializes a task-owned PostgreSQL binary distribution under `.runtime/postgres/pgsql`, on loopback port 55432. It never installs a Windows service or modifies an existing cluster. Obtain the official EDB PostgreSQL 16 binary archive first. The script stores private native settings in `.runtime/local-config.json`; load those values locally without printing them. Do not use this convenience cluster as a production installation.

## Local model and second laptop

`python scripts/setup_models.py` obtains the versions and checksums in `research/models.lock.json`. On Windows, start the pinned `llama-server.exe` with one slot, 8,192 context tokens, four CPU threads, `--reasoning off`, an explicit model alias, loopback binding, and `--api-key-file` pointing at a generated private file. Use Q4_K_M for the selected model. Set `LLM_ENABLED=true`, `LLM_URL`, `LLM_MODEL`, `LLM_API_KEY`, and the timeout on the explanation worker. The API also reads these settings when reporting configuration. Keep the key outside repository history.

For inference on a second laptop, expose only an authenticated HTTPS endpoint. Configure a certificate valid for its hostname and trust its CA through `LLM_CA_FILE` if necessary. Set the matching HTTPS URL and API key; never disable certificate verification. Firewall access to the coordinator host. The native loopback model server can sit behind a local TLS reverse proxy. The same HTTPS boundary applies when containers access host inference. The `llm` hostname is reserved for a private container network; do not use it as an untrusted remote DNS shortcut.

The process generates explanations only. It never receives raw logs, executes recommendations, changes detector decisions, or falls back to an external model. CPU latency and memory must be measured on the actual laptop. A 1.7B model does not imply interactive response times under contention.

## Migration, backup, and rollback

Before migration, stop producers and take a database backup plus consistent copies of each agent SQLite database using the SQLite backup API. Copying only a live `.db` file without its WAL can lose committed work. Preserve private enrollment files separately with restricted access.

The initial Alembic migration creates `ts_` tables. It preserves original prototype tables and archives legacy signal/alert records with `research_eligible=false`. Existing source identities are not automatically trusted. No old arbitrary API key is accepted by the new API. Enrollment is explicit. Validate record counts before and after migration.

For Compose, create a custom-format PostgreSQL backup without binary shell redirection:

```sh
docker compose exec -T postgres pg_dump -U threatscope -d threatscope -Fc -f /tmp/threatscope.dump
docker compose cp postgres:/tmp/threatscope.dump .runtime/threatscope.dump
```

Restore into a newly created database or isolated cluster first. Use `pg_restore --exit-on-error` and verify counts, credential hashes, evidence histories, and migrations before switching traffic. Never restore over a working database as a routine test. Keep the original database untouched until verification succeeds. Schema downgrade intentionally refuses destructive reversal; rollback means restoring the verified backup with its matching application revision.

## Failure handling

An unavailable database returns unsuccessful readiness and ingestion; agents retain pending signals. A worker crash rolls back unfinished work, then resumes from the durable inbox. Do not run multiple correlation owners: the second process fails its advisory-lock check. Slow browser clients disconnect and recover through their cursor. Inference failure invokes bounded repair/fallback. A revoked browser account loses active stream access. Missing source evidence leaves an unresolved outcome.

Agent queues are bounded but historical state has no automatic deletion policy. Review disk usage and retention before sustained deployment. Every organization must retain its own ledger across restarts; replacing it resets its local history and is an operator recovery decision, not an allowed budget-reset method.
