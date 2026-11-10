# ThreatScope

ThreatScope is a research prototype for policy-controlled security evidence sharing, deterministic correlation, and local explanations. Organization agents keep raw events local, release a finite catalogue of derived values, and retain a durable release ledger. A PostgreSQL coordinator records signals before acknowledging them. Independent workers correlate evidence and prepare recipient-scoped explanations.

**A supported rule is not proof of compromise.** Derived values still reveal activity patterns. Release costs are policy units, not differential-privacy guarantees. Current experiments use labeled synthetic organization partitions; they do not establish production scalability or publication novelty.

## Revised research drafts

The two independent IEEE-style manuscripts are editable in LaTeX and available as PDFs. Each numbered version has its stated page count. The drafts report measured pilot results and their limits; neither claims an acceptance outcome.

| Paper | 6 pages | 8 pages | 10 pages | 12 pages |
| --- | --- | --- | --- | --- |
| Framework and evidence disclosure | [PDF](research/papers/paper1/paper1-6pages.pdf) | [PDF](research/papers/paper1/paper1-8pages.pdf) | [PDF](research/papers/paper1/paper1-10pages.pdf) | [PDF](research/papers/paper1/paper1-12pages.pdf) |
| Evidence-grounded local explanations | [PDF](research/papers/paper2/paper2-6pages.pdf) | [PDF](research/papers/paper2/paper2-8pages.pdf) | [PDF](research/papers/paper2/paper2-10pages.pdf) | [PDF](research/papers/paper2/paper2-12pages.pdf) |

The corresponding `.tex` source files sit beside each PDF. [Evidence and contribution notes](research/Contribution-and-Evidence-Matrix.md) and [reference audit](research/Reference-Audit.md) document the research boundary. Authors should review every claim and adapt the selected version to the venue template and disclosure rules before submission.

References revised on 7 October 2026: Paper 1 has 14 cited references and Paper 2 has 17. The audit records the disposition of all 20 supplied review entries and 16 separate-list entries. The [citation register](research/paper-reference-register.json) maps each numbered source to its in-text uses and supported claim. All eight PDFs were rebuilt, checked for missing citations, and visually reviewed; [validation records](research/papers/validation.json) include exact page counts and file hashes.

## Run the evaluation demo

Use Docker Desktop with the Linux engine running and Python 3.12. In PowerShell,
run these commands from the repository root. Stop if any command reports an error.

```powershell
docker info
if (-not (Test-Path .env)) { python scripts/bootstrap.py }
docker compose up -d --build --wait backend correlation explanations frontend
if (-not (Test-Path .runtime/private/demo-credentials.json)) {
    docker compose --profile setup run --rm enroll
}
docker compose --profile evaluation run --rm --build evaluate
```

The last command sends synthetic authentication failures from three separately
enrolled organizations. It waits for a **new** supported incident, policy-approved
evidence, and a completed explanation. It prints the incident ID and result.
The evaluation uses temporary local ledgers for synthetic observations only.
Keep the continuous demo agents stopped while running it.

Open <http://127.0.0.1:5173>. Open
`.runtime/private/demo-credentials.json` privately and use the email and password
under `admin`. Select the newly created authentication incident, show its
evidence and request history, and click **Generate explanation**. With inference
disabled, **Structured fallback** is the expected result. It uses the same
authorized evidence contract and makes no model or cloud request. A supported
rule is evidence for investigation; it does not prove compromise.

For a second rehearsal, rerun the last command. Check the services with
`docker compose ps -a` and
`docker compose logs --tail 100 backend correlation explanations frontend`.
If ports 8000 or 5173 are occupied, stop the conflicting local stack before
starting this one. Keep the database, `.env`, and credentials together; do
not delete volumes or rerun enrollment to reset credentials. Stop services
with `docker compose stop` when finished.

## Run the continuous simulator

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
