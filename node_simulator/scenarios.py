"""Seeded local scenarios and finite aggregates; ground-truth labels never enter wire messages."""
import random
from datetime import datetime

from node_simulator.feature_extractor import extract_features
from node_simulator.log_generator import EventType, RawEvent

SCENARIOS = ("normal", "auth_attack", "provider_outage", "traffic_attack", "flash_crowd")


def events_for(scenario: str, seed: int, duration: int, end: datetime) -> list[RawEvent]:
    if scenario not in SCENARIOS:
        raise ValueError("unknown_scenario")
    rng = random.Random(seed)
    rate = 200 if scenario in {"auth_attack", "provider_outage"} else (
        800 if scenario in {"traffic_attack", "flash_crowd"} else 30
    )
    events = []
    for _ in range(rate * duration):
        failed = scenario in {"auth_attack", "provider_outage"} and rng.random() < 0.8
        status = 503 if failed and scenario == "provider_outage" else 401 if failed else 200
        if scenario == "traffic_attack" and rng.random() < 0.65:
            status = 503
        events.append(RawEvent(
            timestamp=end, event_type=EventType.FAILED_AUTH if failed else EventType.HTTP_REQUEST,
            source_ip=f"192.0.2.{rng.randrange(1, 51)}", endpoint="/synthetic",
            status_code=status, response_time_ms=rng.uniform(10, 1000), is_failed_auth=failed,
        ))
    return events


def catalogue_values(events: list[RawEvent], duration: int) -> tuple[object, dict]:
    """Only enumerated derived values can be passed to the release authority."""
    features = extract_features(events, window_seconds=duration)
    rejected = sum(e.is_failed_auth and e.status_code in {401, 403} for e in events)
    unavailable = sum(e.is_failed_auth and e.status_code >= 500 for e in events)
    kind = "rejected" if rejected and not unavailable else "unavailable" if unavailable and not rejected else (
        "mixed" if rejected or unavailable else "unknown"
    )
    return features, {
        "auth_failure": "high" if features.failed_login_rate > 0.5 else "low",
        "source_spread": "wide" if features.unique_ip_count >= 10 else "narrow",
        "failure_kind": kind,
        "request_rate": "spike" if features.request_rate > 500 else (
            "elevated" if features.request_rate > 100 else "normal"
        ),
        "service_errors": "high" if features.error_rate_5xx > 0.3 else "low",
    }
