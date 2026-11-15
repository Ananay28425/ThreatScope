"""Read downloaded source files locally and write only an aggregate replay profile."""
import argparse
import csv
import io
import json
import math
from itertools import islice
from pathlib import Path
from statistics import median
from zipfile import ZipFile


def rows(archive, name, limit=None):
    with ZipFile(archive) as z, z.open(name) as source:
        yield from islice(csv.DictReader(io.TextIOWrapper(source, encoding="utf-8-sig")), limit)


def bounded(n):
    return max(3, min(12, round(n)))


def profile(directory):
    flows = list(rows(directory / "ids.csv.zip", "02-20-2018.csv", 20_000))
    urls = list(rows(directory / "phishing.zip", "phishing_url_dataset_unique.csv"))
    domains = list(rows(directory / "ai2026.zip", "3_malicious_domains.csv"))
    reports = json.loads((directory / "witfoo.json").read_text(encoding="utf-8"))["rows"]
    attacked = sum(r["Label"].startswith("DDoS") for r in flows)
    flagged_urls = sum(r["label"] == "1" for r in urls)
    domain_votes = sum(int(r["Malicious_Votes"] or 0) > 0 for r in domains)
    suspicion = median(r["row"]["suspicion_score"] for r in reports)
    forward_bytes = median(int(r["TotLen Fwd Pkts"]) for r in flows)
    return {
        "baseline_counts": {
            "authentication_burst": 8,
            "traffic_burst": bounded(6 * attacked / len(flows)),
            "phishing_links": bounded(10 * flagged_urls / len(urls)),
            "malware_checkins": bounded(12 * (domain_votes / len(domains) + suspicion) / 2 + 2),
            "data_transfer": bounded(3 + math.log10(1 + forward_bytes)),
        },
        "sample_summary": {
            "ids_sample_flows": len(flows), "ids_ddos_labels": attacked, "ids_median_forward_bytes": forward_bytes,
            "phishing_urls": len(urls), "phishing_flagged_labels": flagged_urls,
            "intelligence_domains": len(domains), "intelligence_domains_with_votes": domain_votes,
            "witfoo_report_sample": len(reports), "witfoo_median_suspicion": suspicion,
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", type=Path)
    parser.add_argument("--output", type=Path, default=Path("replay/source-profile.json"))
    args = parser.parse_args()
    args.output.write_text(json.dumps(profile(args.source_directory), indent=2) + "\n", encoding="utf-8")
