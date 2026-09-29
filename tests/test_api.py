"""Real HTTP contract tests for authentication, correlation, revisions, and scoped retrieval."""
from datetime import timedelta

from sqlalchemy import func, select

from backend.app.correlation import process_pending
from backend.app.tables import Credential, Evidence, Incident, Signal
from common.contracts import utcnow
from node_simulator.ledger import Ledger
from tests.conftest import login
from tests.test_protocol import signal


async def send_three(system, tmp_path):
    end = utcnow()
    ledgers = []
    for index in range(3):
        item = signal().model_copy(update={"observation_end": end, "observation_start": end - timedelta(seconds=10)})
        ledger = Ledger(tmp_path / f"org{index}.db")
        ledger.queue_signal(item, {"auth_failure": "high", "source_spread": "wide", "failure_kind": "rejected"})
        ledgers.append(ledger)
        response = await system["client"].post("/api/v1/signals", json=item.model_dump(mode="json"),
                                              headers={"X-Api-Key": system["keys"][index]})
        assert response.status_code == 202, response.text
    async with system["db"].sessions() as db, db.begin():
        await process_pending(db, system["settings"])
    return ledgers


async def finish_requests(system, ledgers):
    for _ in range(5):
        for index, ledger in enumerate(ledgers):
            headers = {"X-Api-Key": system["keys"][index]}
            pending = await system["client"].get("/api/v1/agent/requests", headers=headers)
            assert pending.status_code == 200
            for request in pending.json()["requests"]:
                answer = ledger.respond(request).model_dump(mode="json")
                response = await system["client"].post("/api/v1/agent/responses", headers=headers, json=answer)
                assert response.status_code == 200, response.text


async def test_forged_credentials_rejected(system):
    response = await system["client"].post("/api/v1/signals", json=signal().model_dump(mode="json"),
                                          headers={"X-Api-Key": "forged-key-not-enrolled"})
    assert response.status_code == 401


async def test_revoked_credentials_rejected(system):
    async with system["db"].sessions() as db, db.begin():
        credential = (await db.execute(select(Credential).limit(1))).scalar_one()
        credential.active = False
    response = await system["client"].get("/api/v1/agent/requests", headers={"X-Api-Key": system["keys"][0]})
    assert response.status_code == 401


async def test_replay_and_conflicting_reuse(system):
    body = signal().model_dump(mode="json")
    headers = {"X-Api-Key": system["keys"][0]}
    for _ in range(3):
        assert (await system["client"].post("/api/v1/signals", json=body, headers=headers)).status_code == 202
    async with system["db"].sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Signal)) == 1
    body["anomaly_score"] = 0.1
    assert (await system["client"].post("/api/v1/signals", json=body, headers=headers)).status_code == 409


async def test_future_timestamp_rejected(system):
    body = signal().model_dump(mode="json")
    future = utcnow() + timedelta(hours=1)
    body.update(observation_end=future.isoformat(), observation_start=(future - timedelta(seconds=10)).isoformat())
    response = await system["client"].post("/api/v1/signals", json=body,
                                          headers={"X-Api-Key": system["keys"][0]})
    assert response.status_code == 422


async def test_invalid_body_does_not_echo_secret(system):
    body = signal().model_dump(mode="json")
    body["password"] = "DO_NOT_ECHO_CANARY"
    response = await system["client"].post("/api/v1/signals", json=body,
                                          headers={"X-Api-Key": system["keys"][0]})
    assert response.status_code == 422
    assert "DO_NOT_ECHO_CANARY" not in response.text


async def test_body_limit(system):
    response = await system["client"].post("/api/v1/signals", content="x" * 17000)
    assert response.status_code == 413


async def test_csrf_and_login_rotation(system):
    first = await login(system["client"])
    cookie = system["client"].cookies.get("threatscope_session")
    second = await login(system["client"])
    assert first["csrf"] != second["csrf"]
    assert cookie != system["client"].cookies.get("threatscope_session")
    del system["client"].headers["X-CSRF-Token"]
    assert (await system["client"].post("/api/v1/auth/logout")).status_code == 403


async def test_three_organizations_reach_supported_and_scope_evidence(system, tmp_path):
    ledgers = await send_three(system, tmp_path)
    await finish_requests(system, ledgers)
    await login(system["client"])
    incidents = (await system["client"].get("/api/v1/incidents")).json()["incidents"]
    assert len(incidents) == 1
    view = incidents[0]
    assert view["outcome"] == "supported"
    assert len(view["evidence"]) == 9
    for key in system["keys"]:
        assert key not in str(view)
    await login(system["client"], "org0@example.test")
    scoped = (await system["client"].get("/api/v1/incidents/" + view["incident_id"])).json()
    assert len(scoped["evidence"]) == 3
    assert "summary" not in scoped
    await login(system["client"], "org3@example.test")
    assert (await system["client"].get("/api/v1/incidents/" + view["incident_id"])).status_code == 404


async def test_withdrawal_invalidates_explanation(system, tmp_path):
    ledgers = await send_three(system, tmp_path)
    await finish_requests(system, ledgers)
    await login(system["client"])
    view = (await system["client"].get("/api/v1/incidents")).json()["incidents"][0]
    job = (await system["client"].post(f"/api/v1/incidents/{view['incident_id']}/explanations")).json()
    async with system["db"].sessions() as db:
        evidence = (await db.execute(select(Evidence).where(Evidence.org_id == system["orgs"][0]).limit(1))).scalar_one()
        evidence_id = evidence.id
    response = await system["client"].post(f"/api/v1/agent/evidence/{evidence_id}/revise",
        json={"version": 1, "withdraw": True}, headers={"X-Api-Key": system["keys"][0]})
    assert response.status_code == 200, response.text
    result = (await system["client"].get("/api/v1/explanations/" + job["job_id"])).json()
    assert result["status"] == "stale" and result["result"] is None


async def test_same_provenance_cannot_create_quorum(system, tmp_path):
    from backend.app.tables import Organization
    async with system["db"].sessions() as db, db.begin():
        for org in (await db.execute(select(Organization))).scalars():
            org.provenance_group = "shared-feed"
    await send_three(system, tmp_path)
    async with system["db"].sessions() as db:
        incident = (await db.execute(select(Incident))).scalar_one()
        assert incident.summary["independent_groups"] == 1
        assert incident.outcome == "unresolved"
