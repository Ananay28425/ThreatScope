"""
Signal Sender — the only component that talks to the outside world.

This is the privacy enforcement point:
  - It receives DetectionResult (anomaly scores, fingerprints)
  - It receives FeatureVector (aggregated statistics)
  - It NEVER has access to the raw RawEvent objects
  - It packages a signal payload and sends it to the backend via HTTP

Run this as a standalone process (one per simulated node):
    python signal_sender.py --node-id org_1 --nodes 1 --interval 5

Or orchestrate multiple nodes:
    python signal_sender.py --nodes 10 --interval 1
"""

import argparse
import time
import threading
import sys
from datetime import datetime, timezone
from uuid import uuid4

import requests
import structlog

from log_generator import LogGenerator, NodeMode
from feature_extractor import extract_features
from detector import LocalDetector

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(),
    ],
)
log = structlog.get_logger(__name__)

BACKEND_URL = "http://localhost:8000"
INGEST_ENDPOINT = f"{BACKEND_URL}/api/signals/ingest"


def run_node(
    node_id: str,
    api_key: str,
    interval_seconds: float = 5.0,
    window_seconds: int = 60,
) -> None:
    """
    Main loop for a single simulated node.

    Every `interval_seconds`, this function:
      1. Collects raw events from the log generator (local only)
      2. Extracts a privacy-safe feature vector
      3. Runs local anomaly detection
      4. Sends only the signal (score + fingerprint + metrics) to the backend
    """
    generator = LogGenerator(
        node_id=node_id,
        mode=NodeMode.MIXED,
        base_rps=random_rps(),
        attack_rps=random_attack_rps(),
    )
    detector = LocalDetector()

    log.info("Node starting", node_id=node_id)

    for raw_events in generator.stream(interval_seconds):
        # Privacy boundary: raw_events never leaves this block
        fv = extract_features(raw_events, window_seconds=window_seconds)
        result = detector.detect(fv)

        # Build the signal payload — only derived data
        payload = {
            "node_id": node_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "anomaly_score": result.anomaly_score,
            "fingerprint": result.fingerprint,
            "confidence": result.confidence,
            "window_seconds": window_seconds,
            "metrics": fv.to_dict(),  # aggregated stats, no raw events
        }

        try:
            resp = requests.post(
                INGEST_ENDPOINT,
                json=payload,
                headers={"X-Api-Key": api_key},
                timeout=5,
            )
            if resp.status_code == 202:
                log.info(
                    "Signal sent",
                    node_id=node_id,
                    score=result.anomaly_score,
                    fingerprint=result.fingerprint or "–",
                    anomalous=result.is_anomalous,
                )
            else:
                log.warning("Backend rejected signal", status=resp.status_code, body=resp.text[:200])
        except requests.exceptions.ConnectionError:
            log.warning("Backend unreachable, will retry next window", node_id=node_id)
        except Exception as exc:
            log.error("Signal send failed", error=str(exc), node_id=node_id)


def random_rps() -> float:
    import random
    return random.uniform(30.0, 100.0)


def random_attack_rps() -> float:
    import random
    return random.uniform(400.0, 1200.0)


def main() -> None:
    parser = argparse.ArgumentParser(description="ThreatScope Node Simulator")
    parser.add_argument("--node-id", default=None, help="Node ID (default: random UUID prefix)")
    parser.add_argument("--api-key", default="dev-key", help="API key for backend auth")
    parser.add_argument("--nodes", type=int, default=1, help="Number of nodes to simulate")
    parser.add_argument("--interval", type=float, default=5.0, help="Window interval in seconds")
    args = parser.parse_args()

    if args.nodes == 1:
        node_id = args.node_id or f"org_{str(uuid4())[:8]}"
        run_node(node_id, args.api_key, args.interval)
    else:
        # Spawn multiple node threads
        threads = []
        for i in range(args.nodes):
            node_id = f"org_{i+1}"
            t = threading.Thread(
                target=run_node,
                args=(node_id, args.api_key, args.interval),
                daemon=True,
            )
            t.start()
            threads.append(t)
            log.info("Spawned node", node_id=node_id)

        log.info(f"Running {args.nodes} node(s). Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("Shutting down node simulator")
            sys.exit(0)


if __name__ == "__main__":
    main()
