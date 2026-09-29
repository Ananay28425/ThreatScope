"""
Feature Extractor — converts a batch of raw events into a local aggregate feature vector.

This module computes local features, not the network release boundary.
Everything computed here is an aggregate statistic over a time window.
No individual event, IP address, username, or payload is preserved.

Both raw events and these detailed features remain local. Only separately
approved finite catalogue representations enter the network protocol.

Feature vector (f):
  [
    request_rate,         # events/sec in the window
    failed_login_rate,    # failures / total events
    unique_ip_count,      # number of distinct source IPs seen
    ip_entropy,           # Shannon entropy of IP distribution (0 = single source, high = diverse)
    user_agent_entropy,   # diversity of user agents (placeholder — use if UA data added)
    error_rate_4xx,       # fraction of 4xx responses
    error_rate_5xx,       # fraction of 5xx responses
    avg_response_time_ms, # mean response latency
  ]
"""

import math
from collections import Counter
from dataclasses import dataclass

from node_simulator.log_generator import RawEvent


@dataclass
class FeatureVector:
    """
    Local aggregate representation of a time window of activity.
    It is not an authorized network message.
    """
    request_rate: float          # events / second
    failed_login_rate: float     # 0.0 – 1.0
    unique_ip_count: int
    ip_entropy: float            # Shannon entropy (nats)
    error_rate_4xx: float        # 0.0 – 1.0
    error_rate_5xx: float        # 0.0 – 1.0
    avg_response_time_ms: float
    window_seconds: int

    def to_dict(self) -> dict:
        return {
            "request_rate": round(self.request_rate, 3),
            "failed_login_rate": round(self.failed_login_rate, 4),
            "unique_ip_count": self.unique_ip_count,
            "ip_entropy": round(self.ip_entropy, 4),
            "error_rate_4xx": round(self.error_rate_4xx, 4),
            "error_rate_5xx": round(self.error_rate_5xx, 4),
            "avg_response_time_ms": round(self.avg_response_time_ms, 2),
            "window_seconds": self.window_seconds,
        }

    def to_array(self) -> list[float]:
        """Returns the feature vector as a plain float list for scikit-learn."""
        return [
            self.request_rate,
            self.failed_login_rate,
            float(self.unique_ip_count),
            self.ip_entropy,
            self.error_rate_4xx,
            self.error_rate_5xx,
            self.avg_response_time_ms,
        ]


def _shannon_entropy(counts: Counter) -> float:
    """
    Compute Shannon entropy (in nats) over a Counter.

    High entropy = many different values (diverse traffic).
    Low entropy  = one dominant value (suspicious concentration).

    For IP entropy:
      - Normal: many diverse IPs → high entropy
      - DDoS from single source: one IP dominates → near-zero entropy
      - Distributed brute force: many IPs but bursting → moderate entropy, high volume
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log(p)
    return entropy


def extract_features(events: list[RawEvent], window_seconds: int = 60) -> FeatureVector:
    """
    Compute the feature vector for a batch of raw events.

    Parameters:
        events:          raw events from the window (not shared externally)
        window_seconds:  duration of the window (for rate calculations)

    Returns:
        FeatureVector — all derived, non-identifying statistics
    """
    if window_seconds <= 0:
        raise ValueError("window_seconds_must_be_positive")
    n = len(events)
    if n == 0:
        return FeatureVector(
            request_rate=0.0,
            failed_login_rate=0.0,
            unique_ip_count=0,
            ip_entropy=0.0,
            error_rate_4xx=0.0,
            error_rate_5xx=0.0,
            avg_response_time_ms=0.0,
            window_seconds=window_seconds,
        )

    ip_counts = Counter(e.source_ip for e in events)
    failed = sum(1 for e in events if e.is_failed_auth)
    errors_4xx = sum(1 for e in events if 400 <= e.status_code < 500)
    errors_5xx = sum(1 for e in events if e.status_code >= 500)
    avg_rt = sum(e.response_time_ms for e in events) / n

    return FeatureVector(
        request_rate=n / window_seconds,
        failed_login_rate=failed / n,
        unique_ip_count=len(ip_counts),
        ip_entropy=_shannon_entropy(ip_counts),
        error_rate_4xx=errors_4xx / n,
        error_rate_5xx=errors_5xx / n,
        avg_response_time_ms=avg_rt,
        window_seconds=window_seconds,
    )
