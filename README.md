# ThreatScope

ThreatScope is a research prototype for policy-controlled security evidence sharing, deterministic correlation, and verified explanations. Organization agents keep raw events local, release a finite catalogue of derived values, and retain a durable release ledger. A PostgreSQL coordinator records signals before acknowledging them. Independent workers correlate evidence and prepare recipient-scoped explanations.

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

Install [uv](https://docs.astral.sh/uv/) and Node.js 22 with npm, then run this from the repository root:

```powershell
uv run --frozen python -m scripts.demo
```

The launcher installs frontend dependencies on the first run, builds React, creates an isolated SQLite coordinator, enrolls three synthetic organizations, and starts the dashboard and both workers. Open **http://127.0.0.1:5173/**. The evaluation session opens automatically. Use Ctrl+C to stop. If another app holds port 5173, add `--port 15173`.

In another terminal, create a sample incident using the three enrolled nodes:

```powershell
uv run --frozen python -m scripts.demo_check
uv run --frozen python -m scripts.demo_check --scenario traffic_attack
```

Run either command or both. If you changed the launcher port, pass the matching `--url http://127.0.0.1:15173`. Open **Investigations**, select the new incident, inspect the evidence and disclosure decisions, and click **Generate explanation**. Both scenarios are synthetic. Each node generates and processes its own local events; the coordinator receives only the versioned signal and policy-approved refinements.

The laptop demo uses a separate database and enrollment under `.runtime/native-demo`. It leaves old databases and Docker volumes alone. PostgreSQL is the coordinator store in the reference architecture and remains available with the [native deployment instructions](docs/deployment.md).

## Use a hosted model API

The demo runs without a model or a key. To enable hosted generation, set the following values in a private `.env` file and restart:

```dotenv
LLM_ENABLED=true
LLM_URL=https://your-provider.example/v1
LLM_MODEL=your-json-capable-chat-model
LLM_API_KEY=your-provider-key
```

Use a provider that supports OpenAI-compatible Chat Completions and JSON object responses. The URL is the API base, without `/chat/completions`. The backend sends categorical findings and temporary evidence aliases, and validates returned claims locally before displaying them. The request still shares those categories with the configured provider. Use the demo with synthetic data. With no API configured, or if the request or verification fails, the dashboard labels the result **Checked template**.

## Develop and verify

```sh
uv sync --frozen
uv run pytest -q
uv run ruff check backend common node_simulator migrations scripts tests research
npm --prefix frontend ci
npm --prefix frontend run lint
npm --prefix frontend run build
```

Set `TEST_DATABASE_URL` to an isolated PostgreSQL test database to run the same API tests with PostgreSQL concurrency semantics. CI verifies SQLite, PostgreSQL, the frontend and the native demo.

- [Architecture and limits](docs/architecture.md)
- [Deployment and recovery](docs/deployment.md)
- [Versioned contracts](docs/contracts.md)
- [Research cases and evidence](research/)
