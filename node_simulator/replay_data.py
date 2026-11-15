"""Deterministic, inert event fixtures and local window detection for the evaluation."""
import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

from common.contracts import Family

ROOT = Path(__file__).resolve().parents[1]
NODES = ("Orion", "Lyra", "Vega")
SCENARIOS = {
    Family.AUTH: "Password guessing",
    Family.TRAFFIC: "Service flooding",
    Family.PHISHING: "Phishing links",
    Family.BEACON: "Repeated malware check-ins",
    Family.EXFIL: "Unusual data transfers",
}
BEHAVIOR = {
    Family.AUTH: "Rejected sign-ins",
    Family.TRAFFIC: "Service errors",
    Family.PHISHING: "Links flagged by mail controls",
    Family.BEACON: "Recurring outbound contacts",
    Family.EXFIL: "Large outbound transfers",
}
WINDOWS = 20
WIDTH = 100
BASELINE = 4
BANDS = ((5, 7), (10, 12), (16, 18))
FIELDS = ("event_id", "replay_second", "organization", "channel", "source_slot", "indicator_present")


def generate(directory: Path) -> list[Path]:
    profile = json.loads((ROOT / "replay/source-profile.json").read_text(encoding="utf-8"))["baseline_counts"]
    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, node in enumerate(NODES):
        rng = random.Random(20261116 + index)
        path = directory / f"{node.lower()}.csv"
        with path.open("w", newline="", encoding="utf-8") as target:
            out = csv.writer(target)
            out.writerow(FIELDS)
            for segment, family in enumerate(SCENARIOS):
                for window in range(WINDOWS):
                    # Orchestrated overlays; reflected in logs before the detector runs.
                    strength = next((b for b, (a, end) in enumerate(BANDS) if a <= window < end), None)
                    baseline = profile[str(family)]
                    flagged = (rng.randint(baseline, baseline + 6) + index if strength is None else
                               rng.randint(69 + strength * 3, 77 + strength * 3) + index)
                    if strength == 1 and index == 2:
                        flagged = rng.randint(baseline, baseline + 6)  # one genuinely quiet participant
                    order = rng.sample(range(WIDTH), WIDTH)
                    marked = set(order[:flagged])
                    for row in range(WIDTH):
                        position = (segment * WINDOWS + window) * WIDTH + row
                        out.writerow((f"{node[:2].lower()}-{position + 1:05}", (segment * WINDOWS + window) * 5,
                                      node, family, rng.randrange(1, 41), int(row in marked)))
        paths.append(path)
    return paths


def load(path: Path) -> list[tuple[Family, int, int, int]]:
    """Keep CSV contents inside the organization adapter; export counts, never rows."""
    groups = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            groups[(int(row["replay_second"]), Family(row["channel"]))].append(row)
    return [
        (family, stamp, sum(row["indicator_present"] == "1" for row in rows),
         len({row["source_slot"] for row in rows if row["indicator_present"] == "1"}))
        for (stamp, family), rows in sorted(groups.items())
    ]


def detect(family: Family, flags: int, sources: int, baseline: list[int]):
    """Fixed replay detector; the local model explains evidence after correlation."""
    mean = statistics.mean(baseline) if baseline else None
    z = (flags - mean) / max(statistics.pstdev(baseline), 1.0) if mean is not None else None
    score = min(flags / 75, 1.0)
    spread = "wide" if sources >= 10 else "narrow"
    if family == Family.AUTH:
        values = {"auth_failure": "high" if flags >= 60 else "low",
                  "source_spread": spread, "failure_kind": "rejected" if flags else "unknown"}
    elif family == Family.TRAFFIC:
        values = {"request_rate": "spike" if flags >= 60 else "normal",
                  "source_spread": spread, "service_errors": "high" if flags >= 60 else "low"}
    else:
        values = {str(family): "high" if flags >= 60 else "low", "source_spread": spread}
    return score, z, values
