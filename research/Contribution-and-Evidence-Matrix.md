# Contribution and evidence matrix

| Paper | Claim | Evidence | Boundary |
|---|---|---|---|
| 1 | Predicate-driven disclosure lowers sharing relative to fixed richer sharing in the no-fault slice | `results/summary.json`, `results/disclosure.csv`: 1,000 strategy/scenario/fault/seed records | Synthetic partitions; no formal differential privacy or field accuracy claim |
| 1 | Durable accounting handles refusal, coarsening, retries, and exhaustion | `tests/test_recovery.py`, `results/disclosure.csv` | No field deployment |
| 2 | Current-snapshot checks reject stale or unauthorized finite-contract claims | `results/claims-Qwen3-4B-Q4_K_M.jsonl`: eight frozen cases across five conditions | Exact tuple support, not unrestricted natural-language truth; no human study |
| 2 | Deterministic fallback preserves allowed observations when local inference fails | Complete condition: 0 unsupported of 46 claims, fallback in all eight cases; API tests | No measured model benefit over templates; median generation 146.7 s on the tested CPU |

Closest work already covers selective sharing, privacy budgets, grounded generation, and revocation. These manuscripts claim the combined protocol semantics and measured implementation behavior only.
