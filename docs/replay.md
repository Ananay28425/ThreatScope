# Evaluating the ThreatScope dashboard

Evaluation 3 shows two original incident types: authentication bursts and traffic bursts. The replay adds three illustrative rules, not three new validated detectors. The localhost run has three enrolled identities and three separate ledgers, but it is still one machine and a single process. PostgreSQL remains the reference deployment; the dashboard launcher uses SQLite.

| Workflow stage | What to show an evaluator |
|---|---|
| Local detection | Chart flag counts per 100 rows. First four quiet windows per organization and scenario supply the baseline; z uses population standard deviation with a minimum denominator of one count. The rule score is `min(flags / 75, 1)`. It is not a probability or an ML confidence score. |
| Signal delivery | Quiet checks stay local. At the default 0.80 threshold, 60 flags trigger the durable node outbox and authenticated coordinator ingestion. The browser shows the assigned IDs and acknowledged status. |
| Correlation | The worker compares distinct enrolled provenance groups in a 120-second observation bucket. The first qualifying signal represents each organization in each case. The chart and signal table can contain additional checks that do not count as extra votes. |
| Evidence release | Open Shared evidence and Disclosure decisions. The coordinator requests finite categorical values; the node's ledger accounts for releases and can refuse or coarsen them. The default fixture exercises approval and missing corroboration. No raw row, source slot, private endpoint, credential, or URL is in the browser payload or model prompt. |
| Explanation | Demo uses the checked template. Local model mode launches a loopback llama-server process on Play, waits for health, asks it to choose useful claim IDs from an authorized catalogue, and checks the selected claims with the same finite verifier. The renderer writes the final text. Pause and completion stop the process owned by this replay. Unacceptable output receives the visibly labeled checked fallback. |

**Quick presentation.** Pick Password guessing and press Play. Watch the first spike produce three reports and a supported case; the second spike has only two reporting groups and stays unresolved; the third spike returns to three. Pause to inspect the exact signal and evidence IDs. A supported outcome means that the scenario's declared rule was satisfied. It is not proof of compromise. Quiet groups, cover differences, and fallback behavior are part of the demonstration. This replay does not measure precision, recall, formal privacy, or field deployment performance.

## Three reproducible logs

[Download the three CSVs](../replay/organization-logs.zip), or run `uv run --frozen python -m scripts.replay_logs` to regenerate them under `.runtime/replay-logs/`. The launcher generates equivalent copies under its state directory when you start it. Each file has exactly 10,000 synthetic telemetry rows plus a header: five scenarios × 20 windows × 100 events. The three scheduled bursts in every scenario are explicit test overlays. The synthetic source slot is locally generated; it is neither a public IP nor a cross-organization identifier. Replay seconds are a display clock; the coordinator receives separate valid observation intervals grouped into 120-second buckets. Playback compresses time. The files are simulated sensor logs, not sampled real organization logs or packet captures.

| Source | How it was used |
|---|---|
| [CSE-CIC-IDS2018](https://www.kaggle.com/datasets/solarmainframe/ids-intrusion-csv) | First 20,000 rows of `02-20-2018.csv`: 19,932 have a DDoS label, median forward bytes 20. Rescaled these aggregates for the flood and transfer baseline bands. This attack-heavy sample does not estimate real prevalence. |
| [Cybersecurity Attacks & Defense Dataset 2026](https://www.kaggle.com/datasets/chuneeb/ai-cybersecurity-threat-dataset-2026) | 48 of 162 entries in the malicious-domain feed recorded a positive vote. Used the aggregate as a weak calibration input for the recurring outbound contact band, not as a beacon label. |
| [Phishing URL Classification Data](https://www.kaggle.com/datasets/dhrubangtalukdar/real-world-phishing-url-classification-data) | 24,406 positive labels among 48,812 rows. Rescaled to a quiet flag baseline; neither URL strings nor domains are copied. |
| [WitFoo Precinct 6](https://huggingface.co/datasets/witfoo/precinct6-cybersecurity-100m) | Median suspicion 0.25 in the first 100 `attack_reports` viewer rows. Used as a calibration input alongside the threat-intelligence summary. No report text was copied. |
| [violentUTF cybersecurity behavior](https://huggingface.co/datasets/theResearchNinja/benchmarkResults_violentUTF_cybersecurityBehavior) | Model evaluation results, not organizational logs. Excluded from the input generation and from performance claims about ThreatScope. |

`scripts.calibrate_replay` recomputes the [committed aggregate profile](../replay/source-profile.json). It expects `ids.csv.zip` containing `02-20-2018.csv`, `phishing.zip`, `ai2026.zip`, and the dataset viewer response `witfoo.json` for `attack_reports/train`, offset 0, length 100. The background noise and attack ratios are intentionally chosen for visibility; they are not prevalence estimates. Password guessing uses a fixed synthetic background.
