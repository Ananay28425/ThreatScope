# Deployment and recovery

## Laptop evaluation

Run `uv run --frozen python -m scripts.demo` from the repository root. It builds the dashboard, migrates an isolated SQLite file, enrolls three demo nodes once, and runs the API and both workers in one loopback process. Use the same state directory to retain incidents and credentials across restarts. Stop the server before backing up that directory. SQLite in this path supports a single demo process and does not provide the reference PostgreSQL deployment's concurrency semantics.

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

Run `npm ci` and `npm run dev` in `frontend`. Its same-origin development proxy defaults to port 8000; set `BACKEND_URL` before starting Vite when using another port. Native browser origins must match `ALLOWED_ORIGINS`.

## Hosted model inference

Set the environment variables in the README for the API and explanation worker. The provider receives only the minimized authorized categories and temporary evidence aliases. The worker checks the returned claims against the original snapshot. Failure produces a deterministic template and does not delay correlation. Keep the API key private.

Historical local-model evaluation tools remain under `research/` and `scripts/setup_models.py` to reproduce the recorded measurements. The laptop launcher does not use them.

## Migration, backup, and rollback

Before migration, stop producers and take a database backup plus consistent copies of each agent SQLite database using the SQLite backup API. Copying only a live `.db` file without its WAL can lose committed work. Preserve private enrollment files separately with restricted access.

The initial Alembic migration creates `ts_` tables. It preserves original prototype tables and archives legacy signal/alert records with `research_eligible=false`. Existing source identities are not automatically trusted. No old arbitrary API key is accepted by the new API. Enrollment is explicit. Validate record counts before and after migration.

For native PostgreSQL, use a custom-format backup:

```sh
pg_dump -Fc -d threatscope -f .runtime/threatscope.dump
```

Restore into a newly created database or isolated cluster first. Use `pg_restore --exit-on-error` and verify counts, credential hashes, evidence histories, and migrations before switching traffic. Never restore over a working database as a routine test. Keep the original database untouched until verification succeeds. Schema downgrade intentionally refuses destructive reversal; rollback means restoring the verified backup with its matching application revision.

## Failure handling

An unavailable database returns unsuccessful readiness and ingestion; agents retain pending signals. A worker crash rolls back unfinished work, then resumes from the durable inbox. Do not run multiple correlation owners: the second process fails its advisory-lock check. Slow browser clients disconnect and recover through their cursor. Inference failure invokes bounded repair/fallback. A revoked browser account loses active stream access. Missing source evidence leaves an unresolved outcome.

Agent queues are bounded but historical state has no automatic deletion policy. Review disk usage and retention before sustained deployment. Every organization must retain its own ledger across restarts; replacing it resets its local history and is an operator recovery decision, not an allowed budget-reset method.
