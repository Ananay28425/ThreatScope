"""Enrolled organization agent: local detection, durable delivery, and policy-approved responses."""
import argparse
import asyncio
import json
import logging
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from common.contracts import Family, SignalIn, utcnow
from node_simulator.detector import LocalDetector
from node_simulator.ledger import Ledger, Policy
from node_simulator.scenarios import SCENARIOS, catalogue_values, events_for

log = logging.getLogger(__name__)


class Agent:
    def __init__(self, url: str, api_key: str, ledger: Ledger, client=None):
        parsed = urlparse(url)
        if parsed.hostname not in {"127.0.0.1", "localhost", "backend"} and parsed.scheme != "https":
            raise ValueError("remote_coordinator_requires_tls")
        self.ledger = ledger
        self.client = client or httpx.AsyncClient(
            base_url=url.rstrip("/"), headers={"X-Api-Key": api_key}, timeout=5, trust_env=False,
        )

    async def tick(self) -> None:
        for record in self.ledger.pending():
            try:
                response = await self.client.post("/api/v1/signals", json=json.loads(record["payload"]))
                if response.status_code in {401, 403}:
                    log.error("node_credential_rejected")
                    return
                self.ledger.finish(
                    record["id"], response.status_code == 202,
                    permanent=response.status_code in {400, 409, 413, 422},
                )
            except httpx.HTTPError:
                self.ledger.finish(record["id"], False)
                log.warning("delivery_deferred")
                return
        try:
            response = await self.client.get("/api/v1/agent/requests")
            response.raise_for_status()
            for request in response.json()["requests"]:
                result = self.ledger.respond(request)
                reply = await self.client.post("/api/v1/agent/responses", json=result.model_dump(mode="json"))
                if reply.status_code not in {200, 409}:
                    log.warning("evidence_delivery_deferred", extra={"status": reply.status_code})
        except (httpx.HTTPError, ValueError, KeyError):
            log.warning("evidence_poll_deferred")


def observe(ledger: Ledger, detector: LocalDetector, scenario: str, seed: int, duration: int, end=None):
    """No raw event or arbitrary metric dictionary is accepted by the network sender."""
    end = end or utcnow()
    raw = events_for(scenario, seed, duration, end)
    features, values = catalogue_values(raw, duration)
    result = detector.detect(features)
    family = Family.AUTH if result.fingerprint == "AUTH_FAIL_BURST" else (
        Family.TRAFFIC if result.fingerprint == "TRAFFIC_SPIKE" else
        Family.UNKNOWN if result.is_anomalous else Family.NONE
    )
    signal = SignalIn(
        signal_id=uuid4(), snapshot_id=uuid4(), observation_start=end - timedelta(seconds=duration),
        observation_end=end, family=family, anomaly_score=result.anomaly_score,
        model_state="ready" if detector._fitted else "warmup", confidence=None,
        policy_version=ledger.policy.version,
    )
    ledger.queue_signal(signal, values)
    return signal


async def run(args):
    credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
    ledger = Ledger(args.state, Policy(snapshot_cap=args.budget, denied=frozenset(args.deny)))
    agent = Agent(args.backend, credentials["api_key"], ledger)
    detector = LocalDetector()
    next_window, index = 0.0, 0
    loop = asyncio.get_running_loop()
    try:
        while args.windows == 0 or index < args.windows or ledger.stats()["pending"]:
            if loop.time() >= next_window and (args.windows == 0 or index < args.windows):
                scenario = args.scenario or SCENARIOS[int(utcnow().timestamp()) // 120 % len(SCENARIOS)]
                await asyncio.to_thread(observe, ledger, detector, scenario, args.seed + index, args.interval)
                index += 1
                next_window = loop.time() + args.interval
            await agent.tick()
            await asyncio.sleep(1)
        # Continue answering requests after the last finite production window.
        for _ in range(8):
            await agent.tick()
            await asyncio.sleep(0.5)
    finally:
        await agent.client.aclose()
    print(json.dumps(ledger.stats()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--backend", default=os.getenv("BACKEND_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--interval", type=int, default=10, choices=range(1, 601), metavar="SECONDS")
    parser.add_argument("--windows", type=int, default=0)
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--budget", type=int, default=6)
    parser.add_argument("--deny", nargs="*", default=[])
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
