"""Recovery and adversarial identity tests that exercise persisted application behavior."""
import asyncio
from datetime import timedelta

from sqlalchemy import func, select

from backend.app.correlation import process_pending
from backend.app.tables import Credential, Evidence, Notification, Signal, User
from common.contracts import utcnow
from tests.conftest import login
from tests.test_api import finish_requests, send_three
from tests.test_protocol import signal


async def test_expired_credential_fails(system):
    async with system['db'].sessions() as db, db.begin():
        credential = (await db.execute(select(Credential).where(Credential.org_id == system['orgs'][0]))).scalar_one()
        credential.expires_at = utcnow() - timedelta(seconds=1)
    reply = await system['client'].get('/api/v1/agent/requests', headers={'X-Api-Key': system['keys'][0]})
    assert reply.status_code == 401


async def test_conflicting_two_existing_identifiers_returns_conflict(system):
    headers = {'X-Api-Key': system['keys'][0]}
    first, second = signal().model_dump(mode='json'), signal().model_dump(mode='json')
    for body in (first, second):
        assert (await system['client'].post('/api/v1/signals', json=body, headers=headers)).status_code == 202
    first['snapshot_id'] = second['snapshot_id']
    assert (await system['client'].post('/api/v1/signals', json=first, headers=headers)).status_code == 409


async def test_concurrent_signal_retries_only_commit_once(system):
    body = signal().model_dump(mode='json')
    async def send():
        return await system['client'].post('/api/v1/signals', json=body, headers={'X-Api-Key': system['keys'][0]})
    replies = await asyncio.gather(*(send() for _ in range(8)))
    assert all(r.status_code == 202 for r in replies)
    async with system['db'].sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Signal)) == 1


async def test_worker_replay_does_not_duplicate_transitions(system, tmp_path):
    ledgers = await send_three(system, tmp_path)
    await finish_requests(system, ledgers)
    async with system['db'].sessions() as db:
        before = await db.scalar(select(func.count()).select_from(Notification))
    for _ in range(3):
        async with system['db'].sessions() as db, db.begin():
            assert await process_pending(db, system['settings']) == 0
    async with system['db'].sessions() as db:
        assert await db.scalar(select(func.count()).select_from(Notification)) == before


async def test_foreign_response_rejected(system, tmp_path):
    ledgers = await send_three(system, tmp_path)
    request = (await system['client'].get('/api/v1/agent/requests', headers={'X-Api-Key': system['keys'][0]})).json()['requests'][0]
    response = ledgers[0].respond(request).model_dump(mode='json')
    reply = await system['client'].post('/api/v1/agent/responses', json=response,
                                       headers={'X-Api-Key': system['keys'][1]})
    assert reply.status_code == 404


async def test_expired_evidence_cannot_support_cached_view(system, tmp_path):
    ledgers = await send_three(system, tmp_path)
    await finish_requests(system, ledgers)
    await login(system['client'])
    async with system['db'].sessions() as db, db.begin():
        evidence = (await db.execute(select(Evidence).limit(1))).scalar_one()
        evidence.created_at = utcnow() - timedelta(days=2)
    view = (await system['client'].get('/api/v1/incidents')).json()['incidents'][0]
    assert view['outcome'] == 'unresolved'
    assert any(not e['active'] for e in view['evidence'])


async def test_disabled_user_session_fails(system):
    await login(system['client'], 'org0@example.test')
    cookie = system['client'].cookies.get('threatscope_session')
    async with system['db'].sessions() as db:
        target = await db.scalar(select(User.id).where(User.org_id == system['orgs'][0]))
    await login(system['client'])
    reply = await system['client'].post('/api/v1/admin/users/' + target + '/disable')
    assert reply.status_code == 200
    system['client'].cookies.clear()
    system['client'].cookies.set('threatscope_session', cookie)
    assert (await system['client'].get('/api/v1/incidents')).status_code == 401
