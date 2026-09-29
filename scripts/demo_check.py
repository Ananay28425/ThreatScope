"""Exercise the real API, three independent local ledgers, worker, and explanation service."""
import asyncio
import json
import time
from pathlib import Path

import httpx

from common.contracts import utcnow
from node_simulator.agent import Agent, observe
from node_simulator.detector import LocalDetector
from node_simulator.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]


async def main():
    credentials = json.loads((ROOT / '.runtime/private/demo-credentials.json').read_text())
    agents = []
    end = utcnow()
    for index, org in enumerate(credentials['organizations']):
        ledger = Ledger(ROOT / f'.runtime/demo-{index}.db')
        observe(ledger, LocalDetector(), 'auth_attack', 71 + index, 10, end=end)
        agents.append(Agent('http://127.0.0.1:18000', org['api_key'], ledger))
    async with httpx.AsyncClient(base_url='http://127.0.0.1:18000', headers={
        'Origin': 'http://127.0.0.1:5173'}, timeout=10, trust_env=False) as client:
        response = await client.post('/api/v1/auth/login', json=credentials['admin'])
        response.raise_for_status()
        client.headers['X-CSRF-Token'] = response.json()['csrf']
        started = time.perf_counter()
        for _ in range(30):
            for agent in agents:
                await agent.tick()
            views = (await client.get('/api/v1/incidents')).json()['incidents']
            if views and views[0]['outcome'] == 'supported':
                break
            await asyncio.sleep(0.5)
        assert views and views[0]['outcome'] == 'supported', 'demo_did_not_reach_supported'
        result = {'incident': views[0], 'decision_seconds': time.perf_counter() - started,
                  'agents': [a.ledger.stats() for a in agents]}
        job = (await client.post('/api/v1/incidents/' + views[0]['incident_id'] + '/explanations')).json()
        for _ in range(260):
            reply = await client.get('/api/v1/explanations/' + job['job_id'])
            reply.raise_for_status()
            explanation = reply.json()
            if explanation['status'] not in {'queued', 'running'}:
                break
            await asyncio.sleep(1)
        assert explanation['status'] in {'complete', 'fallback'}, explanation['status']
        result['explanation'] = explanation
        (ROOT / '.runtime/demo-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps({'outcome': result['incident']['outcome'], 'evidence': len(views[0]['evidence']),
                          'decision_seconds': result['decision_seconds'], 'explanation': explanation['status']}))
    for agent in agents:
        await agent.client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
