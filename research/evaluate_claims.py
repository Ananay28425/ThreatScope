"""Measure bounded local claim generation and replay its outputs against changed authorization state."""
import argparse
import asyncio
import hashlib
import json
import time
from pathlib import Path

import httpx

from backend.app.config import Settings
from backend.app.explanations import check_claims, claim_key, expected_claims, generate_raw
from common.contracts import ClaimSet

ROOT = Path(__file__).resolve().parents[1]


def score(raw, view):
    """Count errors within the finite contract; never claim general natural-language truth."""
    accepted, errors = check_claims(raw, view)
    try:
        count = len(ClaimSet.model_validate(raw).claims)
    except ValueError:
        count = 0
    expected = {claim_key(c) for c in expected_claims(view)}
    covered = len({claim_key(c) for c in accepted} & expected)
    return {'claims': count, 'unsupported': max(0, count - len(accepted)),
            'contract_invalid': int('invalid_claim_contract' in errors),
            'coverage': covered / len(expected), 'errors': errors}


async def main(args):
    data = (ROOT / 'research/cases.json').read_bytes()
    expected_hash = (ROOT / 'research/cases.sha256').read_text().strip()
    assert hashlib.sha256(data).hexdigest() == expected_hash, 'frozen_cases_changed'
    config = json.loads((ROOT / '.runtime/local-config.json').read_text())
    settings = Settings(llm_enabled=True, llm_url='http://127.0.0.1:18080/v1',
                        llm_api_key=config['llm_api_key'], llm_model=args.model,
                        llm_timeout_seconds=120)
    async with httpx.AsyncClient(timeout=2, trust_env=False) as readiness:
        for attempt in range(90):
            try:
                response = await readiness.get('http://127.0.0.1:18080/health',
                    headers={'Authorization': 'Bearer ' + config['llm_api_key']})
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
        else:
            raise RuntimeError('model_not_ready_before_measurement')
    output = ROOT / 'research/results' / ('claims-' + args.model + '.jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = {json.loads(line)['case'] for line in output.read_text().splitlines()} if output.exists() else set()
    for case in json.loads(data)['claim_cases']:
        if case['name'] in completed:
            continue
        result = {'case': case['name'], 'model': args.model, 'cases_sha256': expected_hash,
                  'initial': case['initial'], 'current': case['current'], 'conditions': {}}
        template_started = time.perf_counter()
        template = {'claims': [c.model_dump() for c in expected_claims(case['current'])]}
        template_score = score(template, case['current'])
        result['conditions']['template'] = {'raw': template, **template_score,
                                           'seconds': time.perf_counter() - template_started}
        for condition in ('direct', 'cited'):
            started = time.perf_counter()
            error = None
            try:
                if case['name'] == 'model_failure':
                    raise TimeoutError('deliberately_unavailable')
                raw = await generate_raw(case['initial'], settings, mode=condition)
            except Exception as exc:
                raw, error = {'claims': []}, type(exc).__name__
            result['conditions'][condition] = {'raw': raw, **score(raw, case['current']),
                                                'seconds': time.perf_counter() - started, 'failure': error}
        # Reuse the citation-prompted output for paired verifier ablation, avoiding model drift.
        raw = result['conditions']['cited']['raw']
        accepted, errors = check_claims(raw, case['initial'])
        verified = {'claims': [c.model_dump() for c in accepted]} if not errors else {
            'claims': [c.model_dump() for c in expected_claims(case['initial'])]}
        result['conditions']['verify_without_lifecycle'] = {'raw': verified, **score(verified, case['current']),
                                                           'fallback': bool(errors)}
        changed = case['initial']['digest'] != case['current']['digest']
        repaired = False
        repair_raw, repair_seconds = None, 0.0
        if errors and not changed and case['name'] != 'model_failure':
            repaired = True
            repair_started = time.perf_counter()
            try:
                raw = await generate_raw(case['current'], settings, repair=errors)
                repair_raw = raw
                accepted, errors = check_claims(raw, case['current'])
            except Exception:
                errors = ['model_unavailable']
            repair_seconds = time.perf_counter() - repair_started
        complete = {'claims': [c.model_dump() for c in accepted]} if not errors and not changed else template
        result['conditions']['complete'] = {'raw': complete, **score(complete, case['current']),
                                            'fallback': bool(errors) or changed, 'repair': repaired,
                                            'invalidated': changed, 'repair_raw': repair_raw,
                                            'repair_seconds': repair_seconds,
                                            'generation_seconds': result['conditions']['cited']['seconds'] + repair_seconds}
        # The complete path regenerates a deterministic current snapshot after invalidation.
        with output.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(result) + '\n')
        print(args.model, case['name'], 'recorded', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='Qwen3-1.7B-Q4_K_M')
    asyncio.run(main(parser.parse_args()))
