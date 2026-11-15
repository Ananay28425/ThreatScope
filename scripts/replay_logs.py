"""Build three 10,000-event organization CSVs without network access."""
import argparse
from pathlib import Path

from node_simulator.replay_data import generate

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".runtime/replay-logs"))
    for path in generate(parser.parse_args().output):
        print(f"{path}: 10,000 events")
