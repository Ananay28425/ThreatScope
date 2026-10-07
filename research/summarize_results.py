"""Summarize recorded measurements without manufacturing unavailable experiment results."""
import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / 'research/results'
    rows = list(csv.DictReader((folder / 'disclosure.csv').open()))
    groups = {}
    for fault in sorted({r['fault'] for r in rows}):
        for strategy in sorted({r['strategy'] for r in rows}):
            subset = [r for r in rows if r['fault'] == fault and r['strategy'] == strategy]
            groups[f'{fault}/{strategy}'] = {
                'cases': len(subset),
                **{key: sum(int(r[key]) for r in subset) for key in (
                    'true_positive', 'false_positive', 'unresolved', 'policy_units', 'refinements', 'payload_bytes')},
                'mean_rounds': statistics.mean(float(r['rounds']) for r in subset),
                'median_local_protocol_seconds': statistics.median(float(r['local_protocol_seconds']) for r in subset),
            }
    claims = {}
    for path in folder.glob('claims-*.jsonl'):
        cases = [json.loads(line) for line in path.read_text().splitlines()]
        conditions = {}
        for condition in ('template', 'direct', 'cited', 'verify_without_lifecycle', 'complete'):
            measurements = [case['conditions'][condition] for case in cases]
            conditions[condition] = {
                'cases': len(cases), 'claims': sum(m['claims'] for m in measurements),
                'unsupported': sum(m['unsupported'] for m in measurements),
                'invalid_contract_cases': sum(m['contract_invalid'] for m in measurements),
                'mean_coverage': statistics.mean(m['coverage'] for m in measurements),
                'failure_cases': sum(bool(m.get('failure')) for m in measurements),
                'fallback_cases': sum(bool(m.get('fallback')) for m in measurements),
                'median_generation_seconds': statistics.median(
                    m.get('seconds', m.get('generation_seconds', 0)) for m in measurements)
                    if condition != 'verify_without_lifecycle' else None,
            }
        claims[path.stem] = conditions
    summary = {'protocol': groups, 'claims': claims,
               'cic_ids2017': {'status': 'not_run', 'reason': 'official archive endpoint returned an HTML registration page'},
               'scope': 'Synthetic protocol evaluation and finite-claim model study. No human usefulness or real-organization accuracy claim.',
               'hashes': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob('*') if p.is_file() and p.name != 'summary.json'}}
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    for key in ('none/fixed_richer', 'none/decision_driven'):
        print(key, groups[key])


if __name__ == '__main__':
    main()
