"""
Log Generator — simulates realistic security event streams for a single organization node.

Generates events across three modes:
  - NORMAL:    baseline traffic (low anomaly scores expected)
  - ATTACK:    simulated brute-force, DDoS, or port scan bursts
  - MIXED:     alternates between normal and attack phases

This is intentionally fake data. The architecture's privacy guarantee
is that even if this were real, raw logs stay here — only derived signals
ever leave this process. That constraint is enforced by signal_sender.py.
"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterator


class EventType(str, Enum):
    LOGIN_ATTEMPT = "login_attempt"
    HTTP_REQUEST = "http_request"
    API_CALL = "api_call"
    FAILED_AUTH = "failed_auth"
    TRAFFIC_SPIKE = "traffic_spike"
    PORT_SCAN = "port_scan"


@dataclass
class RawEvent:
    """
    Represents a raw log entry. This NEVER leaves the node.
    Only derived statistics computed from a window of these events are shared.
    """
    timestamp: datetime
    event_type: EventType
    # Simulated IP (for local feature computation only — not shared externally)
    source_ip: str
    endpoint: str
    status_code: int
    response_time_ms: float
    is_failed_auth: bool = False


class NodeMode(str, Enum):
    NORMAL = "normal"
    ATTACK = "attack"
    MIXED = "mixed"


class LogGenerator:
    """
    Generates a realistic stream of security events for a simulated organization.

    Configuration knobs (all tunable per node to create diversity):
      - base_rps:      baseline requests/sec in normal mode
      - attack_rps:    requests/sec during an attack burst
      - fail_rate:     baseline auth failure rate (0–1)
      - attack_fail:   auth failure rate during attack (0–1)
      - ip_pool_size:  number of distinct IPs in the simulation (entropy control)
    """

    def __init__(
        self,
        node_id: str,
        mode: NodeMode = NodeMode.MIXED,
        base_rps: float = 50.0,
        attack_rps: float = 800.0,
        fail_rate: float = 0.05,
        attack_fail_rate: float = 0.75,
        ip_pool_size: int = 200,
    ) -> None:
        self.node_id = node_id
        self.mode = mode
        self.base_rps = base_rps
        self.attack_rps = attack_rps
        self.fail_rate = fail_rate
        self.attack_fail_rate = attack_fail_rate
        self.ip_pool_size = ip_pool_size

        # Track current simulation phase
        self._in_attack = False
        self._attack_ends_at: float = 0.0

        # Realistic-looking IP pools
        self._normal_ips = [f"192.168.{random.randint(1, 50)}.{random.randint(1, 254)}"
                            for _ in range(ip_pool_size)]
        self._attack_ips = [f"{random.randint(1, 223)}.{random.randint(0,255)}"
                            f".{random.randint(0,255)}.{random.randint(1,254)}"
                            for _ in range(ip_pool_size * 5)]  # attacker has many IPs

        self._endpoints = [
            "/api/login", "/api/data", "/api/export",
            "/admin", "/api/users", "/health", "/api/auth/refresh",
        ]

    def _is_attack_phase(self) -> bool:
        now = time.time()
        if self.mode == NodeMode.NORMAL:
            return False
        if self.mode == NodeMode.ATTACK:
            return True
        # MIXED: random attack windows
        if self._in_attack:
            if now > self._attack_ends_at:
                self._in_attack = False
        elif random.random() < 0.002:  # ~0.2% chance per event to start attack
            self._in_attack = True
            self._attack_ends_at = now + random.uniform(30, 120)  # 30–120 sec burst
        return self._in_attack

    def _generate_event(self, attack: bool) -> RawEvent:
        fail_rate = self.attack_fail_rate if attack else self.fail_rate
        ip_pool = self._attack_ips if attack else self._normal_ips
        is_fail = random.random() < fail_rate

        return RawEvent(
            timestamp=datetime.now(timezone.utc),
            event_type=EventType.FAILED_AUTH if is_fail else random.choice(list(EventType)),
            source_ip=random.choice(ip_pool),
            endpoint=random.choice(self._endpoints),
            status_code=401 if is_fail else random.choices(
                [200, 200, 200, 301, 404, 500], weights=[60, 10, 10, 5, 10, 5]
            )[0],
            response_time_ms=random.gauss(
                800 if attack else 120,
                200 if attack else 30,
            ),
            is_failed_auth=is_fail,
        )

    def stream(self, interval_seconds: float = 1.0) -> Iterator[list[RawEvent]]:
        """
        Yields batches of events, one batch per interval.
        The batch size is proportional to the current RPS mode.
        """
        while True:
            attack = self._is_attack_phase()
            rps = self.attack_rps if attack else self.base_rps
            batch_size = max(1, int(rps * interval_seconds))
            events = [self._generate_event(attack) for _ in range(batch_size)]
            yield events
            time.sleep(interval_seconds)
