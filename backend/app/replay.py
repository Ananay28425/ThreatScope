"""Loopback-only evaluation replay. Uses the real ingest, evidence and correlation paths."""
import asyncio
import json
import logging
import random
import secrets
import subprocess
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from backend.app.explanations import expected_claims, explain
from backend.app.http_api import session_dependency
from backend.app.security import actor
from backend.app.snapshots import snapshot
from backend.app.tables import Incident, Organization, Participation, Signal, User
from common.contracts import SignalIn, utcnow
from node_simulator.agent import Agent
from node_simulator.ledger import Ledger
from node_simulator.replay_data import BASELINE, BEHAVIOR, NODES, SCENARIOS, WINDOWS, detect, load

router = APIRouter(prefix="/api/v1/replay", tags=["evaluation"])
log = logging.getLogger(__name__)


class LocalModel:
    """Own exactly one llama-server process; never attach to another running server."""

    def __init__(self, executable: Path, model: Path, port: int, state: Path):
        self.executable, self.model, self.port, self.state = executable, model, port, state
        self.url = f"http://127.0.0.1:{port}/v1"
        self.process = None
        self.api_key = secrets.token_urlsafe(32)

    async def start(self):
        if self.process and self.process.returncode is None:
            return
        try:
            _, occupied = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", self.port), 1)
        except OSError:
            pass
        else:
            occupied.close()
            await occupied.wait_closed()
            raise RuntimeError(f"Model port {self.port} is already in use. Choose another --model-port.")
        with (self.state / "replay-model.log").open("wb") as output:
            self.process = await asyncio.create_subprocess_exec(
                str(self.executable), "-m", str(self.model), "--host", "127.0.0.1",
                "--port", str(self.port), "--alias", "threatscope-replay", "-c", "4096", "--api-key", self.api_key,
                stdout=output, stderr=subprocess.STDOUT,
            )
        async with httpx.AsyncClient(timeout=2, trust_env=False,
                                     headers={"Authorization": "Bearer " + self.api_key}) as client:
            for _ in range(100):
                if self.process.returncode is not None:
                    break
                try:
                    response = await client.get(self.url.removesuffix("/v1") + "/health")
                    if response.status_code == 200 and self.process.returncode is None:
                        models = await client.get(self.url + "/models")
                        if models.is_success and any(
                            m.get("id") == "threatscope-replay" for m in models.json().get("data", [])
                        ):
                            return
                except (httpx.HTTPError, ValueError):
                    pass
                await asyncio.sleep(0.5)
        raise RuntimeError("Local model did not become ready. Check replay-model.log in the state directory.")

    async def select_claims(self, snapshot, settings, **_kwargs):
        """Ask the model to select useful permitted claims without generating evidence text."""
        candidates = expected_claims(snapshot)
        available = [
            {"id": i, "kind": claim.kind, "fact": claim.predicate, "value": claim.value}
            for i, claim in enumerate(candidates, 1)
        ]
        payload = {
            "model": settings.llm_model, "max_tokens": 64, "temperature": 0,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "replay_claim_selection",
                "schema": {"type": "object", "properties": {"ids": {
                    "type": "array", "items": {"type": "integer", "enum": list(range(1, len(candidates) + 1))},
                    "minItems": 1, "maxItems": 4,
                }}, "required": ["ids"], "additionalProperties": False},
            }},
            "messages": [
                {"role": "system", "content": "Choose one to four useful claim IDs for the security "
                 "analyst. Prefer the outcome and evidence. Return JSON like {\"ids\":[1,4]}."},
                {"role": "user", "content": json.dumps(available, separators=(",", ":"))},
            ],
        }
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds, trust_env=False) as client:
            reply = await client.post(self.url + "/chat/completions", json=payload,
                                      headers={"Authorization": "Bearer " + self.api_key})
            reply.raise_for_status()
            if len(reply.content) > 16_384:
                raise ValueError("Oversized model response")
            ids = json.loads(reply.json()["choices"][0]["message"]["content"])["ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 4 or
                any(type(i) is not int or not 1 <= i <= len(candidates) for i in ids) or len(set(ids)) != len(ids)):
            raise ValueError("Invalid claim selection")
        return {"claims": [candidates[i - 1].model_dump() for i in ids]}

    async def stop(self):
        process, self.process = self.process, None
        if not process or process.returncode is not None:
            return
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), 4)
        except TimeoutError:
            process.kill()
            await process.wait()
        except ProcessLookupError:
            await process.wait()


class Replay:
    def __init__(self, directory, logs_dir, model=None):
        self.directory, self.logs_dir, self.model = directory, logs_dir, model
        self.credentials = json.loads((directory / "demo-credentials.json").read_text(encoding="utf-8"))
        self.mode, self.scenario, self.state = "demo", "all", "idle"
        self.rows, self.points, self.cases, self.events = deque(maxlen=100), [], [], deque(maxlen=12)
        self.task = None
        self.lock = asyncio.Lock()
        self.position, self.total, self.owner_id = 0, 0, None
        self.error = ""
        self.jobs = {}

    def view(self):
        return {
            "mode": self.mode, "scenario": self.scenario, "state": self.state,
            "model_configured": self.model is not None,
            "position": self.position, "total": self.total, "error": self.error,
            "labels": SCENARIOS, "metrics": BEHAVIOR, "nodes": NODES, "rows": list(self.rows),
            "points": self.points, "cases": self.cases, "events": list(self.events),
        }

    async def command(self, app, user, body):
        async with self.lock:
            if body.action == "pause":
                await self.halt()
                return
            if body.action == "reset":
                await self.halt()
                self.position, self.total, self.state = 0, 0, "idle"
                self.rows.clear()
                self.points, self.cases, self.error = [], [], ""
                self.events.clear()
                return
            if self.task and not self.task.done():
                return
            if body.mode == "live" and not self.model:
                raise HTTPException(409, "Configure --llama-server and --model at launch to use the local model.")
            if self.state not in {"paused", "error"} or (
                self.mode, self.scenario, self.owner_id
            ) != (body.mode, body.scenario, user.id):
                await self.setup(app, user, body)
            self.error = ""
            self.state = "starting" if self.mode == "live" else "playing"
            self.task = asyncio.create_task(self.run(app))

    async def setup(self, app, user, body):
        self.mode, self.scenario, self.owner_id = body.mode, body.scenario, user.id
        self.logs = await asyncio.to_thread(lambda: {
            node: [row for row in load(self.logs_dir / (node.lower() + ".csv"))
                   if body.scenario == "all" or row[0] == body.scenario] for node in NODES
        })
        self.total, self.position = len(self.logs[NODES[0]]) * len(NODES), 0
        self.rows.clear()
        self.points, self.cases = [], []
        self.events.clear()
        self.jobs, self.keys, self.baselines = {}, set(), {}
        self.run_id = uuid4().hex
        self.ledgers = {node: Ledger(self.directory / "replay-ledgers" / (node.lower() + ".db")) for node in NODES}
        settings = app.state.settings
        clock = int(utcnow().timestamp()) // settings.window_seconds
        async with app.state.database.sessions() as db:
            used = set((await db.scalars(select(Incident.correlation_key))).all())
        candidates = list(range(max(16, 600 // settings.window_seconds),
                                int(20 * 3600 / settings.window_seconds) - 15))
        random.SystemRandom().shuffle(candidates)
        for offset in candidates:
            start = clock - offset - 15
            if not any(f"{family}:{bucket}" in used for bucket in range(start, start + 15) for family in SCENARIOS):
                self.bucket = start
                break
        else:
            raise HTTPException(409, "No unused replay window is available. Start a new state directory.")
        self.event("Replay prepared", "Raw rows were read by three local adapters.")

    def event(self, title, detail):
        self.events.appendleft({"title": title, "detail": detail, "id": uuid4().hex})

    async def halt(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.state = "paused"
            self.event("Paused", "No new windows will be checked until you resume.")
        if self.model:
            await self.model.stop()

    async def step(self, app, agents):
        node = NODES[self.position % len(NODES)]
        index = self.position // len(NODES)
        window = index % WINDOWS
        family, stamp, flags, sources = self.logs[node][index]
        base = self.baselines.setdefault((node, family), [])
        score, z, values = detect(family, flags, sources, base if len(base) >= BASELINE else [])
        if window < BASELINE:
            base.append(flags)
        self.points.append({"node": node, "window": index + 1, "count": flags, "family": family})
        row = {
            "id": f"check-{self.run_id[:5]}-{self.position + 1:03}", "node": node, "scenario": family,
            "window": index + 1, "replay_second": stamp, "z": round(z, 2) if z is not None else None,
            "score": round(score, 2), "state": "Local only", "signal_id": None, "case": None,
        }
        settings = app.state.settings
        if score >= settings.score_threshold:
            bucket = self.bucket + index // WINDOWS * 3 + window // 7
            key = f"{family}:{bucket}"
            end = datetime.fromtimestamp(bucket * settings.window_seconds + 5, timezone.utc)
            signal = SignalIn(
                signal_id=uuid4(), snapshot_id=uuid4(), observation_start=end - timedelta(seconds=5),
                observation_end=end, family=family, anomaly_score=score, detector_version="replay-rules/1",
            )
            ledger = self.ledgers[node]
            if ledger.queue_signal(signal, values):
                row.update(state="Queued for delivery", signal_id=str(signal.signal_id), case=key)
                self.keys.add(key)
                self.rows.appendleft(row)
                self.position += 1
                await agents[node].tick()
                return
            row["state"] = "Held by policy"
        self.rows.appendleft(row)
        self.position += 1

    async def sync(self, app):
        if not self.keys:
            return []
        async with app.state.database.sessions() as db:
            user = await db.get(User, self.owner_id)
            records = (await db.scalars(select(Incident).where(Incident.correlation_key.in_(self.keys))
                                       .order_by(Incident.created_at.desc()))).all()
            ids = [row["signal_id"] for row in self.rows if row["signal_id"]]
            signals = (await db.scalars(select(Signal).where(Signal.external_id.in_(ids)))).all()
            enrolled = (await db.execute(select(Signal.external_id).join(
                Participation, Participation.signal_id == Signal.id,
            ).where(Signal.external_id.in_(ids)))).scalars().all()
            names = (await db.execute(select(Participation.incident_id, Organization.name).join(
                Organization, Organization.id == Participation.org_id,
            ).where(Participation.incident_id.in_([record.id for record in records])).order_by(Organization.name))).all()
            cases = {record.correlation_key: await snapshot(db, user, record.id) for record in records}
            for case in cases.values():
                case["reporting_nodes"] = [name for case_id, name in names if case_id == case["incident_id"]]
        old = {case["incident_id"]: case for case in self.cases}
        checked = {signal.external_id: signal.processed for signal in signals}
        for row in self.rows:
            sid = row["signal_id"]
            case = cases.get(row["case"])
            if sid in checked:
                row["state"] = ("Used in case" if sid in enrolled else "Checked") if checked[sid] else "Accepted"
                if case:
                    row["incident_id"] = case["incident_id"]
        for case in cases.values():
            before = old.get(case["incident_id"], {})
            if before.get("outcome") != case["outcome"] or before.get("version") != case["version"]:
                self.event(SCENARIOS[case["family"]], f"{case['summary']['independent_groups']} of 3 groups · "
                           f"{len(case['evidence'])} evidence releases · {case['outcome']}")
            item = self.jobs.get((case["incident_id"], case["digest"]))
            if item and item.done() and not item.cancelled():
                case["explanation"] = item.result()
            elif not item and case["outcome"] in {"supported", "contradicted"}:
                case["explanation_status"] = "Waiting to check explanation"
            elif item:
                case["explanation_status"] = "Checking model output" if self.mode == "live" else "Checking template"
        self.cases = list(cases.values())
        return self.cases

    async def run(self, app):
        agents = {}
        finished = False
        config = app.state.settings.model_copy(update={"llm_enabled": False})
        try:
            if self.mode == "live":
                await self.model.start()
                config = config.model_copy(update={
                    "llm_enabled": True, "llm_url": self.model.url, "llm_model": "threatscope-replay",
                    "llm_api_key": self.model.api_key, "llm_ca_file": None,
                })
                self.event("Local model ready", "Only authorized evidence will be sent to it.")
            self.state = "playing"
            for org in self.credentials["organizations"]:
                client = httpx.AsyncClient(base_url="http://127.0.0.1", transport=httpx.ASGITransport(app=app),
                                            headers={"X-Api-Key": org["api_key"]})
                agents[org["name"]] = Agent("http://127.0.0.1", org["api_key"], self.ledgers[org["name"]], client)
            idle, cycles = 0, 0
            while True:
                if self.mode == "live" and self.model.process.returncode is not None:
                    raise RuntimeError("Local model stopped unexpectedly. Check replay-model.log.")
                if self.position < self.total:
                    await self.step(app, agents)
                    idle = 0
                else:
                    idle += 1
                if cycles % 6 == 0 or idle:
                    cases = await self.sync(app)
                    waiting = any(c["summary"]["independent_groups"] >= app.state.settings.quorum and
                                  c["outcome"] == "unresolved" and
                                  c["reason"] in {"missing_evidence"} for c in cases)
                    if waiting:
                        for agent in agents.values():
                            await agent.tick()
                    for c in cases:
                        if c["outcome"] not in {"supported", "contradicted"}:
                            continue
                        key = (c["incident_id"], c["digest"])
                        if key not in self.jobs and not any(not job.done() for job in self.jobs.values()):
                            model_input = {key: value for key, value in c.items() if key not in {
                                "reporting_nodes", "explanation", "explanation_status",
                            }}
                            generator = self.model.select_claims if self.mode == "live" else None
                            self.jobs[key] = asyncio.create_task(explain(model_input, config, generator=generator))
                    if idle >= 8 and not waiting and all(
                        (c["incident_id"], c["digest"]) in self.jobs and
                        self.jobs[(c["incident_id"], c["digest"])].done()
                        for c in cases if c["outcome"] in {"supported", "contradicted"}
                    ):
                        await self.sync(app)
                        finished = True
                        return
                cycles += 1
                await asyncio.sleep(0.18 if not idle else 0.4)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.state, self.error = "error", str(exc) if isinstance(exc, RuntimeError) else "Replay could not finish."
            log.exception("Replay failed")
        finally:
            pending = [job for job in self.jobs.values() if not job.done()]
            for job in pending:
                job.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            self.jobs = {key: job for key, job in self.jobs.items() if not job.cancelled()}
            for agent in agents.values():
                await agent.client.aclose()
            if self.model:
                await self.model.stop()
            if finished:
                self.state = "complete"
                self.event("Replay finished", "Case results and explanations remain available for inspection.")


class Control(BaseModel):
    action: str
    mode: str = "demo"
    scenario: str = "all"


async def access(request, db):
    replay = getattr(request.app.state, "replay", None)
    if not replay:
        raise HTTPException(404, "Replay is only available from the local launcher.")
    user = await actor(request, db)
    if user.role not in {"admin", "coordinator"}:
        raise HTTPException(403, "Coordinator access required.")
    return replay, user


@router.get("")
async def status(request: Request, db=Depends(session_dependency)):
    replay, _ = await access(request, db)
    if replay.state in {"paused", "complete"} and not replay.lock.locked():
        async with replay.lock:
            await replay.sync(request.app)
    return replay.view()


@router.post("")
async def control(body: Control, request: Request, db=Depends(session_dependency)):
    replay, user = await access(request, db)
    if (body.action not in {"play", "pause", "reset"} or body.mode not in {"demo", "live"} or
            body.scenario not in {"all", *SCENARIOS}):
        raise HTTPException(422, "Invalid replay control.")
    await db.close()  # Release the browser session transaction before coordinating replay writes.
    await replay.command(request.app, user, body)
    return replay.view()
