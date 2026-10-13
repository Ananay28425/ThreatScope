# Combined manuscript reference and claim map

Updated 14 October 2026. All four versions cite the same 30 unique entries in first-citation order. Standards and dataset records are identified as such. Older primary studies remain where they establish direct prior art.

| No. | Key | Primary source | Supported claim and boundary |
|---|---|---|---|
| 1 | `nist150` | [Primary record](https://doi.org/10.6028/NIST.SP.800-150) | Sharing participation and handling rules are explicit governance decisions; no measured performance claim. |
| 2 | `misp` | [Primary record](https://doi.org/10.1145/2994539.2994542) | Collaborative structured CTI exchange is established prior work. |
| 3 | `freudiger` | [Primary record](https://doi.org/10.1007/978-3-319-20550-2_17) | Controlled sharing and collaborator selection precede this work; published record replaces the earlier arXiv-only reference. |
| 4 | `stix` | [Primary record](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) | Threat-information representation; this implementation does not claim STIX compliance. |
| 5 | `lincoln` | [Primary record](https://www.usenix.org/conference/13th-usenix-security-symposium/privacy-preserving-sharing-and-correlation-security-alerts) | Sanitized sharing and correlation of security alerts are longstanding prior art. |
| 6 | `sepia` | [Primary record](https://www.usenix.org/conference/usenixsecurity10/sepia-privacy-preserving-aggregation-multi-domain-network-events-and) | Secure aggregation of multi-domain network events; policy-unit accounting does not provide its cryptographic protection. |
| 7 | `psi` | [Primary record](https://www.usenix.org/conference/nsdi26/presentation/arpaci) | Over-threshold private set intersection for collaborative intrusion detection; our categorical disclosure is a different mechanism. |
| 8 | `kum` | [Primary record](https://www.usenix.org/conference/soups2019/presentation/kum) | Incremental on-demand disclosure has prior empirical work in record linkage; results are not transferred to security detection. |
| 9 | `bouwman` | [Primary record](https://www.usenix.org/conference/usenixsecurity22/presentation/bouwman) | Empirical community study distinguishes aggregation of existing intelligence from added coverage; does not validate our provenance classifier. |
| 10 | `hackphyr` | [Primary record](https://arxiv.org/abs/2409.11276) | Local cybersecurity model capability, specifically a red-team agent; not evidence of analyst explanation quality. |
| 11 | `redsage` | [Primary record](https://openreview.net/pdf?id=W4FAenIrQ2) | Locally deployable cybersecurity-generalist model; local deployment alone is not our novelty. The conference PDF and [author preprint](https://arxiv.org/abs/2601.22159v2) confirm the publication status. |
| 12 | `alce` | [Primary record](https://aclanthology.org/2023.emnlp-main.398/) | Citation-bearing generation and citation-quality evaluation. |
| 13 | `rarr` | [Primary record](https://aclanthology.org/2023.acl-long.910/) | Post-generation evidence attribution and revision are existing techniques. |
| 14 | `factscore` | [Primary record](https://aclanthology.org/2023.emnlp-main.741/) | Atomic factual-support evaluation; our finite tuple score is not its general factuality metric. |
| 15 | `lexis` | [Primary record](https://www.techscience.com/cmc/v89n2/68791/html) | Structured security-report drafts from XAI evidence are close prior work. |
| 16 | `investigation` | [Primary record](https://doi.org/10.1109/BigData66926.2025.11402161) | Agentic alert investigation with constrained queries; [author preprint](https://arxiv.org/abs/2604.25846) confirms the publication relationship. |
| 17 | `gsar` | [Primary record](https://arxiv.org/abs/2604.23366) | Typed grounding and bounded recovery are adjacent prior art; preprint status is retained. |
| 18 | `revocation` | [Primary record](https://arxiv.org/abs/2609.08258) | Soft revocation labels can leave memory authoritative; no claim that our pilot replicates its benchmark. |
| 19 | `securityshap` | [Primary record](https://arxiv.org/abs/2602.19087) | SHAP-based detector interpretation differs from recipient-authorized factual claim admission. |
| 20 | `refchecker` | [Primary record](https://aclanthology.org/2024.emnlp-main.395/) | Reference-based claim-triplet checking; our verifier instead uses exact finite tuples and current authorization. |
| 21 | `selfcheck` | [Primary record](https://aclanthology.org/2023.emnlp-main.557/) | Sampling consistency as a hallucination signal; consistency does not establish recipient permission. |
| 22 | `faithlm` | [Primary record](https://aclanthology.org/2026.eacl-long.177/) | Intervention-based explanation faithfulness differs from fidelity to an authorized evidence snapshot. |
| 23 | `cicpaper` | [Primary record](https://doi.org/10.5220/0006639801080116) | Dataset construction and labelled traffic context. Our CIC replay remains incomplete. |
| 24 | `cicdata` | [Primary record](https://www.unb.ca/cic/datasets/ids-2017.html) | Official dataset description and access source, separate from the dataset paper. |
| 25 | `dwork` | [Primary record](https://doi.org/10.1561/0400000042) | Formal differential privacy is distinct from operator-defined disclosure costs. |
| 26 | `cce` | [Primary record](https://doi.org/10.1109/SRDS69199.2025.00022) | Serverless SIEM correlation is an architectural alternative; our single-worker results do not imply elasticity. [Author-hosted manuscript](https://di.fc.ul.pt/~imedeiros/papers/SRDS2025_CCE.pdf). |
| 27 | `injection` | [Primary record](https://doi.org/10.1145/3605764.3623985) | Instructions inside retrieved data create indirect prompt-injection risks. The DOI registration confirms published metadata; [author preprint](https://arxiv.org/abs/2302.12173) provides open content. |
| 28 | `confidential` | [Primary record](https://www.usenix.org/conference/atc23/presentation/vaswani) | Hardware confidentiality and host isolation differ from ordinary local CPU execution. |
| 29 | `qwen3` | [Primary record](https://arxiv.org/abs/2505.09388) | Model-family identity and thinking modes; no imported performance result. |
| 30 | `offloading` | [Primary record](https://doi.org/10.1145/3704413.3764429) | Quality/latency/cost trade-offs in local–cloud serving; our fixed local pilot does not evaluate offloading. [Author preprint](https://arxiv.org/abs/2502.11007). |

The 31-entry union loses only `dara`, a broad position paper, because the combined argument retains more direct primary sharing methods. No source is included solely to meet a count. Metadata was cross-checked through Undermind; publisher records retain the published year/DOI when discovery resolves an earlier preprint. Offloading metadata remains supported by the prior publisher/source audit, with its author preprint rechecked separately.

Full-text checks in this revision cover GSAR, revocation and threshold PSI. LEXIS's full PDF was unavailable through Undermind; the publisher HTML is the available full-text source. The register is a scoped claim map, not certification of every result in the cited papers.
