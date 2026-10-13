# Contribution and evidence matrix

Active scope, 14 October 2026: one combined research manuscript. Disclosure/correlation and local interpretation are components of the same evidence lifecycle. The recorded studies remain separate. The GTSS 2027 manuscript is a preserved exception.

| Component | Claim | Evidence | Boundary |
|---|---|---|---|
| Disclosure/correlation | Predicate-driven disclosure lowers sharing relative to fixed richer sharing in the no-fault slice | `results/summary.json`, `results/disclosure.csv`: 1,000 strategy/scenario/fault/seed records | Synthetic partitions; no formal differential privacy or field accuracy claim |
| Disclosure/correlation | Durable accounting handles refusal, coarsening, retries, and exhaustion | `tests/test_recovery.py`, `results/disclosure.csv` | No field deployment |
| Local interpretation | Current-snapshot checks reject stale or unauthorized finite-contract claims | `results/claims-Qwen3-4B-Q4_K_M.jsonl`: eight frozen cases across five conditions | Exact tuple support, not unrestricted natural-language truth; no human study |
| Local interpretation | Deterministic fallback preserves allowed observations when local inference fails | Complete condition: 0 unsupported of 46 claims, fallback in all eight cases; API tests | No measured model benefit over templates; median generation 146.7 s on the tested CPU |
| Common evidence lifecycle | Disclosure, authorization and report invalidation compose through versioned records | Implemented service contracts; manuscript method and worked trace | No matched full-path experiment or analyst study; the two component totals do not establish a joint effect |

Closest work already covers selective sharing, privacy budgets, grounded generation, and revocation. The combined manuscript claims the specified protocol semantics and recorded component behavior only.
