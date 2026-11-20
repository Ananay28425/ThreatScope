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

## Run without Docker

Install [uv](https://docs.astral.sh/uv/), Python 3.12 or newer, and Node.js 22 with npm. Docker and a separate PostgreSQL server are not required for the laptop demo.

For a fresh checkout:

```powershell
git clone https://github.com/Ananay28425/ThreatScope.git
cd ThreatScope
uv sync --frozen
npm --prefix frontend ci
```

For an existing checkout, commit or stash your own changes before switching branches, then update:

```powershell
git switch main
git pull --ff-only origin main
```

Start from the repository root:

```powershell
uv run --frozen python -m scripts.demo
```

Open **http://127.0.0.1:15173/**. The launcher builds the frontend, enrolls Orion, Lyra and Vega, and starts the dashboard and workers without Docker. In **Workflow replay**, choose a scenario and press **Play**. Pause freezes input; Reset clears the replay display. Cases remain in **Incident archive**. **System info** explains every dashboard metric. In another terminal, `uv run --frozen python -m scripts.demo_check` still runs the original CLI smoke check.

Keep the terminal open while using the dashboard. Press **Ctrl+C** to stop the app and its workers. After the first successful build, you can reuse the frontend build:

```powershell
uv run --frozen python -m scripts.demo --no-build
```

If port 15173 is occupied, use a different port and match it in the smoke check:

```powershell
uv run --frozen python -m scripts.demo --port 15174
# In another terminal:
uv run --frozen python -m scripts.demo_check --url http://127.0.0.1:15174
```

Open **http://127.0.0.1:15174/** for that example. Run without `--no-build` after frontend changes. The laptop database and logs stay under `.runtime/native-demo`. PostgreSQL remains the reference deployment; see [native deployment](docs/deployment.md).

### Run the same replay with a local model

Install a llama.cpp release that includes `llama-server` and download an instruction-tuned GGUF. On Windows:

```powershell
uv run --frozen python -m scripts.demo --llama-server "D:\llama.cpp\llama-server.exe" --model "D:\models\your-model.gguf"
```

Select **Local model simulation**, then press **Play**. ThreatScope starts its own loopback model server, checks that it is ready, and stops it on Pause, completion, or app shutdown. You do not need to start a separate service. Use `--model-port` if the default 18081 is occupied. The model is used for explaining evidence; it does not drive activity detection or case outcomes. If its claims fail validation, the screen shows **Checked fallback**. Neither replay mode contacts a hosted API, even when one is configured for the separate Incident archive.

[Download the three 10,000-row CSVs](replay/organization-logs.zip). [Replay methods, source mapping and evaluator walkthrough](docs/replay.md) describe exactly what is synthetic and what the dashboard proves.

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
