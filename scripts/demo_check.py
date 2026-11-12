"""Drive a synthetic incident through the running API and verify its explanation."""

import argparse
import asyncio
import json
import secrets
import time
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from common.contracts import utcnow
from node_simulator.agent import Agent, observe
from node_simulator.detector import LocalDetector
from node_simulator.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]


async def run(args):
    credentials = json.loads(args.credentials.read_text(encoding="utf-8"))
    started = time.monotonic()
    async with httpx.AsyncClient(
        base_url=args.url, headers={"Origin": args.origin}, timeout=8, trust_env=False,
    ) as client:
        login = await client.post("/api/v1/auth/login", json=credentials["admin"])
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf"]
        initial = await client.get("/api/v1/incidents", params={"limit": 100})
        initial.raise_for_status()
        old_ids = {i["incident_id"] for i in initial.json()["incidents"]}

        # Use the same synthetic observation time for all nodes and spread repeat
        # rehearsals over historical buckets so they don't reuse the live window.
        end = utcnow() - timedelta(seconds=secrets.randbelow(12 * 3600))
        with TemporaryDirectory(prefix="threatscope-demo-") as temp:
            agents = []
            try:
                for index, org in enumerate(credentials["organizations"]):
                    ledger = Ledger(Path(temp) / f"agent-{index}.db")
                    observe(ledger, LocalDetector(), args.scenario, 71 + index, 10, end=end)
                    agents.append(Agent(args.agent_url or args.url, org["api_key"], ledger))
                if len(agents) != 3:
                    raise RuntimeError("Evaluation requires three enrolled organizations.")

                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    for agent in agents:
                        await agent.tick()
                    response = await client.get("/api/v1/incidents", params={"limit": 100})
                    response.raise_for_status()
                    incident = next((
                        i for i in response.json()["incidents"]
                        if i["incident_id"] not in old_ids and i["outcome"] == "supported"
                        and i["summary"]["supporting_groups"] == 3
                        and i["evidence"] and i["requests"]
                    ), None)
                    if incident and all(not agent.ledger.stats()["pending"] for agent in agents):
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise RuntimeError(
                        "No fresh supported incident with three provenance groups. "
                        "Check backend and correlation logs, then rerun."
                    )

                decision_seconds = time.monotonic() - started
                reply = await client.post(f"/api/v1/incidents/{incident['incident_id']}/explanations")
                reply.raise_for_status()
                job_id = reply.json()["job_id"]
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    reply = await client.get(f"/api/v1/explanations/{job_id}")
                    reply.raise_for_status()
                    explanation = reply.json()
                    if explanation["status"] not in {"queued", "running"}:
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise RuntimeError("Explanation did not finish. Check explanation worker logs.")

                if explanation["status"] not in {"complete", "fallback"} or not explanation["result"]:
                    raise RuntimeError(f"Unexpected explanation status: {explanation['status']}")
                if args.output:
                    args.output.parent.mkdir(parents=True, exist_ok=True)
                    args.output.write_text(json.dumps({
                        "incident": incident, "decision_seconds": decision_seconds,
                        "agents": [agent.ledger.stats() for agent in agents], "explanation": explanation,
                    }, indent=2), encoding="utf-8")
                print(json.dumps({
                    "incident_id": incident["incident_id"],
                    "outcome": incident["outcome"],
                    "supporting_groups": incident["summary"]["supporting_groups"],
                    "evidence": len(incident["evidence"]),
                    "decision_seconds": round(decision_seconds, 2),
                    "explanation": explanation["status"],
                }))
            finally:
                for agent in agents:
                    await agent.client.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--agent-url", help="Direct coordinator URL when the dashboard uses a proxy.")
    parser.add_argument("--origin", help="Defaults to the dashboard URL.")
    parser.add_argument("--credentials", type=Path, default=ROOT / ".runtime/native-demo/demo-credentials.json")
    parser.add_argument("--scenario", choices=["auth_attack", "traffic_attack"], default="auth_attack")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=35)
    args = parser.parse_args()
    args.origin = args.origin or args.url
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
