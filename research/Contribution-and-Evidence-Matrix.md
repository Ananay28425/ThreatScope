# Contribution and evidence matrix

| Paper | Claim | Evidence | Boundary |
|---|---|---|---|
| 1 | Predicate-driven disclosure lowers sharing in the no-fault protocol slice | `results/summary.json`, 1,000 deterministic cases | Synthetic partitions; no formal differential privacy |
| 1 | Durable accounting handles refusal, coarsening, retries, and exhaustion | `tests/test_recovery.py`, `results/disclosure.csv` | No field deployment |
| 2 | Version and authorization checks reject unsupported or stale claims | `results/claims-Qwen3-4B-Q4_K_M.jsonl` | Two cases per model condition; no human study |
| 2 | Local fallback preserves verified observations when inference fails | complete-condition pilot and API tests | CPU latency is high |

Closest work already covers selective sharing, privacy budgets, grounded generation, and revocation. These manuscripts claim the combined protocol semantics and measured implementation behavior only.
