"""Behavioral tests for atomic release accounting and immutable disclosure retries."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from common.contracts import Family, SignalIn, utcnow
from node_simulator.ledger import Ledger, Policy


def signal():
    end = utcnow()
    return SignalIn(signal_id=uuid4(), snapshot_id=uuid4(), observation_start=end - timedelta(seconds=10),
                    observation_end=end, family=Family.AUTH, anomaly_score=0.92)


def request(item, entry="source_spread"):
    return {"schema_version": 1, "request_id": str(uuid4()), "snapshot_id": str(item.snapshot_id),
            "entry": entry, "recipient": "coordinator", "deadline": (utcnow() + timedelta(seconds=60)).isoformat()}


def test_concurrent_retries_charge_once(tmp_path):
    ledger = Ledger(tmp_path / "agent.db")
    item = signal()
    ledger.queue_signal(item, {"source_spread": "wide"})
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ledger.respond(request(item)), range(24)))
    assert len({str(r.evidence_id) for r in results}) == 1
    assert ledger.stats()["released_units"] == 3


def test_policy_version_does_not_reset_budget(tmp_path):
    ledger = Ledger(tmp_path / "agent.db", Policy(snapshot_cap=2))
    item = signal()
    ledger.queue_signal(item, {"auth_failure": "high", "source_spread": "wide"})
    assert ledger.respond(request(item, "auth_failure")).status == "approved"
    ledger.policy = replace(ledger.policy, version=2)
    assert ledger.respond(request(item)).reason == "budget"
    assert Ledger(ledger.path, ledger.policy).stats()["released_units"] == 2


def test_policy_revocation_blocks_cached_retransmission(tmp_path):
    ledger = Ledger(tmp_path / "agent.db")
    item = signal()
    ledger.queue_signal(item, {"source_spread": "wide"})
    assert ledger.respond(request(item)).status == "approved"
    ledger.policy = replace(ledger.policy, denied=frozenset({"source_spread"}), version=2)
    assert ledger.respond(request(item)).reason == "policy"


def test_initial_release_and_overlapping_snapshots_share_rolling_cap(tmp_path):
    ledger = Ledger(tmp_path / "agent.db", Policy(rolling_hour_cap=1))
    assert ledger.queue_signal(signal(), {})
    assert not ledger.queue_signal(signal(), {})
    assert ledger.stats()["gaps"]["initial_release_budget"] == 1


def test_coarsening_names_actual_representation(tmp_path):
    ledger = Ledger(tmp_path / "agent.db", Policy(coarsened=frozenset({"source_spread"})))
    item = signal()
    ledger.queue_signal(item, {"source_spread": "wide"})
    result = ledger.respond(request(item))
    assert (result.status, result.value, result.cost) == ("coarsened", "unknown", 0)


def test_expired_request_never_releases(tmp_path):
    ledger = Ledger(tmp_path / "agent.db")
    item = signal()
    ledger.queue_signal(item, {"source_spread": "wide"})
    query = request(item)
    query["deadline"] = (utcnow() - timedelta(seconds=1)).isoformat()
    assert ledger.respond(query).reason == "expired"
    assert ledger.stats()["released_units"] == 1


def test_outbox_survives_restart_and_retries_same_payload(tmp_path):
    ledger = Ledger(tmp_path / "agent.db")
    item = signal()
    ledger.queue_signal(item, {})
    original = ledger.pending()[0]
    recovered = Ledger(ledger.path).pending()[0]
    assert recovered["payload"] == original["payload"]
    ledger.finish(str(item.signal_id), True)
    assert Ledger(ledger.path).pending() == []


@pytest.mark.parametrize("field,value", [("ip_address", "CANARY_IP"), ("password", "CANARY_SECRET")])
def test_raw_fields_rejected(field, value):
    body = signal().model_dump(mode="json")
    body[field] = value
    with pytest.raises(ValueError):
        SignalIn.model_validate(body)


def test_invalid_snapshot_metric_is_not_stored(tmp_path):
    ledger = Ledger(tmp_path / "agent.db")
    with pytest.raises(ValueError):
        ledger.queue_signal(signal(), {"CANARY_SECRET": "high"})
    assert ledger.stats()["released_units"] == 0
