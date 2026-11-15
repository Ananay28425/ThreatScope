import csv
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from backend.app.correlation import source_decision
from node_simulator.replay_data import NODES, SCENARIOS, detect, generate, load


def test_published_logs_match_generator_and_preserve_missing_corroboration(tmp_path):
    paths = generate(tmp_path)
    archive = Path(__file__).resolve().parents[1] / "replay/organization-logs.zip"
    decisions = Counter()
    with ZipFile(archive) as shipped:
        for node, path in zip(NODES, paths, strict=True):
            assert shipped.read(path.name) == path.read_bytes()
            with path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == len({row["event_id"] for row in rows}) == 10_000
            assert {row["organization"] for row in rows} == {node}
            for family, stamp, flags, spread in load(path):
                score, _, disclosure = detect(family, flags, spread, [])
                if score >= 0.8:
                    assert source_decision(family, disclosure) == "supported"
                    decisions[family, stamp % 100] += 1
    for family in SCENARIOS:
        assert {stamp: count for (group, stamp), count in decisions.items() if group == family} == {
            25: 3, 30: 3, 50: 2, 55: 2, 80: 3, 85: 3,
        }
