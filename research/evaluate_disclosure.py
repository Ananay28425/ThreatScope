"""Controlled protocol-level comparisons using production detection, catalogue rules, and release ledgers."""
import csv
import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.app.correlation import choose_entry, source_decision
from common.contracts import PREDICATES, Family, SignalIn, utcnow
from node_simulator.detector import LocalDetector
from node_simulator.ledger import Ledger, Policy
from node_simulator.scenarios import catalogue_values, events_for

ROOT = Path(__file__).resolve().parents[1]
STRATEGIES = ('local_only', 'fixed_minimal', 'fixed_richer', 'static_escalation', 'decision_driven')


def run_case(scenario, seed, strategy, fault, folder):
    started = time.perf_counter()
    observed = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    decisions, total_bytes, rounds, units, releases = [], 0, 0, 0, 0
    for node in range(3):
        features, values = catalogue_values(events_for(scenario, seed * 3 + node, 10, observed), 10)
        detection = LocalDetector().detect(features)
        family = Family.AUTH if detection.fingerprint == 'AUTH_FAIL_BURST' else (
            Family.TRAFFIC if detection.fingerprint == 'TRAFFIC_SPIKE' else Family.NONE)
        signal = SignalIn(signal_id=uuid5(NAMESPACE_URL, f'{scenario}/{seed}/{node}/signal'),
            snapshot_id=uuid5(NAMESPACE_URL, f'{scenario}/{seed}/{node}/snapshot'),
            observation_start=observed - timedelta(seconds=10), observation_end=observed,
            family=family, anomaly_score=detection.anomaly_score)
        if family == Family.NONE or detection.anomaly_score < 0.8:
            decisions.append('none')
            continue
        if strategy == 'local_only':
            decisions.append('supported')
            continue
        policy = Policy(snapshot_cap=2 if fault == 'budget' else 6,
                        denied=frozenset({'failure_kind', 'service_errors'}) if fault == 'deny' else frozenset(),
                        coarsened=frozenset({'source_spread'}) if fault == 'coarse' else frozenset())
        ledger = Ledger(folder / f'{node}.db', policy)
        ledger.queue_signal(signal, values)
        total_bytes += len(signal.model_dump_json().encode())
        if strategy == 'fixed_minimal':
            decisions.append('supported')
        else:
            disclosed, attempted, node_rounds = {}, set(), 0
            ordered = list(PREDICATES[family])
            while len(attempted) < len(ordered):
                entry = choose_entry(family, disclosed, attempted) if strategy == 'decision_driven' else ordered[len(attempted)]
                if entry is None:
                    break
                request = {'schema_version': 1, 'request_id': str(uuid5(NAMESPACE_URL, f'{scenario}/{seed}/{node}/{entry}')),
                    'snapshot_id': str(signal.snapshot_id), 'entry': entry, 'recipient': 'coordinator',
                    'deadline': (utcnow() + timedelta(minutes=5)).isoformat()}
                response = ledger.respond(request)
                total_bytes += len(json.dumps(request, separators=(',', ':')).encode()) + len(response.model_dump_json().encode())
                attempted.add(entry)
                node_rounds += 1
                if response.status != 'denied':
                    disclosed[entry] = response.value
                    releases += 1
                elif strategy == 'decision_driven':
                    break
            rounds = max(rounds, 1 if strategy == 'fixed_richer' else node_rounds)
            decisions.append(source_decision(family, disclosed))
        units += ledger.stats()['released_units']
    outcome = 'supported' if decisions.count('supported') == 3 else (
        'contradicted' if decisions.count('contradicted') == 3 else 'none' if decisions.count('none') == 3 else 'unresolved')
    truth = scenario in {'auth_attack', 'traffic_attack'}
    return {'scenario': scenario, 'seed': seed, 'strategy': strategy, 'fault': fault, 'attack': int(truth),
            'outcome': outcome, 'true_positive': int(truth and outcome == 'supported'),
            'false_positive': int(not truth and outcome == 'supported'), 'unresolved': int(outcome == 'unresolved'),
            'policy_units': units, 'refinements': releases, 'payload_bytes': total_bytes, 'rounds': rounds,
            'local_protocol_seconds': time.perf_counter() - started}


def main():
    data = (ROOT / 'research/cases.json').read_bytes()
    assert hashlib.sha256(data).hexdigest() == (ROOT / 'research/cases.sha256').read_text().strip()
    manifest = json.loads(data)
    output = ROOT / 'research/results/disclosure.csv'
    if output.exists():
        raise RuntimeError('measurement_output_exists')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w', newline='') as stream:
        writer = None
        for fault in ('none', 'deny', 'coarse', 'budget'):
            for seed in manifest['seeds']:
                for scenario in manifest['scenarios']:
                    for strategy in STRATEGIES:
                        folder = ROOT / f'.runtime/protocol/{fault}/{seed}/{scenario}/{strategy}'
                        row = run_case(scenario, seed, strategy, fault, folder)
                        if writer is None:
                            writer = csv.DictWriter(stream, fieldnames=row)
                            writer.writeheader()
                        writer.writerow(row)
            stream.flush()
            print('Recorded', fault, flush=True)


if __name__ == '__main__':
    main()
