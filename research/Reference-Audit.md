# Reference audit and claim map

**Active update, 14 October 2026:** the combined manuscript uses 30 references from the prior 31-entry union. Its current citation order and claim map are in [`papers/combined/Reference-and-Claim-Map.md`](papers/combined/Reference-and-Claim-Map.md). The sections below retain the 7 October source audits and historical split. Only the broad `dara` position paper is omitted from the combined bibliography; direct primary methods remain. The GTSS manuscript is separately preserved.

Revision date: **7 October 2026**. Paper 1 now has **14** references and Paper 2 has **17**, with in-text citations in every length variant. The previous drafts had seven and nine. The additions address missing direct prior work, rather than treating a reference-count target as evidence of research quality.

The authoritative bibliographies are in `papers/paper1/core.tex` and `papers/paper2/body.tex`. They use IEEE-style numbered references ordered by first citation. Published versions are preferred when verified; arXiv entries are explicitly identifiable as preprints. Page ranges and DOI identifiers are included where the authoritative record provides them. A standard or dataset page is cited as such, rather than presented as a research article. Long author lists may use *et al.* in the manuscript; this is a citation convention, not missing authorship.

Verification has two distinct levels: bibliographic records establish identity and publication metadata; the cited text must support the associated claim. The map below identifies the narrow claim for which each source is used. It does not certify all claims made by a source, establish novelty by itself, or substitute external results for this repository's measured results. Abstract-only access does not establish a full-method comparison. The detailed source metadata from the supplied corpus is retained in `reference-metadata.json`; the current manuscript register is `paper-reference-register.json`.

## Paper 1: framework and evidence disclosure

| Citation key | Verified source | Supported claim and boundary |
|---|---|---|
| `nist150` | [NIST SP 800-150, 2016](https://doi.org/10.6028/NIST.SP.800-150) | Sharing participation and handling rules are explicit governance decisions; no measured performance claim. |
| `misp` | [Wagner et al., ACM WISCS 2016](https://doi.org/10.1145/2994539.2994542) | Collaborative structured CTI exchange is established prior work. |
| `freudiger` | [Freudiger, De Cristofaro and Brito, DIMVA 2015, pp. 327–349](https://doi.org/10.1007/978-3-319-20550-2_17) | Controlled sharing and collaborator selection precede this work; published record replaces the earlier arXiv-only reference. |
| `stix` | [OASIS STIX 2.1 standard, 10 June 2021](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html) | Threat-information representation; this implementation does not claim STIX compliance. |
| `lincoln` | [Lincoln, Porras and Shmatikov, USENIX Security 2004](https://www.usenix.org/conference/13th-usenix-security-symposium/privacy-preserving-sharing-and-correlation-security-alerts) | Sanitized sharing and correlation of security alerts are longstanding prior art. |
| `sepia` | [Burkhart et al., USENIX Security 2010](https://www.usenix.org/conference/usenixsecurity10/sepia-privacy-preserving-aggregation-multi-domain-network-events-and) | Secure aggregation of multi-domain network events; policy-unit accounting does not provide its cryptographic protection. |
| `psi` | [Arpaci, Boutaba and Kerschbaum, NSDI 2026, pp. 2211–2226](https://www.usenix.org/conference/nsdi26/presentation/arpaci) | Over-threshold private set intersection for collaborative intrusion detection; our categorical disclosure is a different mechanism. |
| `dara` | [Dara and Muralidhara, arXiv:1602.02452](https://arxiv.org/abs/1602.02452) | Position paper on privacy problems and cryptographic collaborative-detection architectures; not treated as an empirical benchmark. |
| `kum` | [Kum et al., SOUPS 2019, pp. 175–189](https://www.usenix.org/conference/soups2019/presentation/kum) | Incremental on-demand disclosure has prior empirical work in record linkage; results are not transferred to security detection. |
| `bouwman` | [Bouwman et al., USENIX Security 2022, pp. 1149–1165](https://www.usenix.org/conference/usenixsecurity22/presentation/bouwman) | Empirical community study distinguishes aggregation of existing intelligence from added coverage; does not validate our provenance classifier. |
| `cicpaper` | [Sharafaldin, Lashkari and Ghorbani, ICISSP 2018, pp. 108–116](https://doi.org/10.5220/0006639801080116) | Dataset construction and labelled traffic context. Our CIC replay remains incomplete. |
| `cicdata` | [UNB CIC-IDS2017 dataset](https://www.unb.ca/cic/datasets/ids-2017.html) | Official dataset description and access source, separate from the dataset paper. |
| `dwork` | [Dwork and Roth, 2014](https://doi.org/10.1561/0400000042) | Formal differential privacy is distinct from operator-defined disclosure costs. |
| `cce` | [Serckumecka, Medeiros and Bessani, IEEE SRDS 2025, pp. 95–105](https://doi.org/10.1109/SRDS69199.2025.00022) | Serverless SIEM correlation is an architectural alternative; our single-worker results do not imply elasticity. [Author-hosted manuscript](https://di.fc.ul.pt/~imedeiros/papers/SRDS2025_CCE.pdf). |

## Paper 2: local AI and evidence validity

| Citation key | Verified source | Supported claim and boundary |
|---|---|---|
| `hackphyr` | [Rigaki, Catania and Garcia, arXiv:2409.11276](https://arxiv.org/abs/2409.11276) | Local cybersecurity model capability, specifically a red-team agent; not evidence of analyst explanation quality. |
| `redsage` | [Suryanto et al., ICLR 2026](https://openreview.net/pdf?id=W4FAenIrQ2) | Locally deployable cybersecurity-generalist model; local deployment alone is not our novelty. The conference PDF and [author preprint](https://arxiv.org/abs/2601.22159v2) confirm the publication status. |
| `alce` | [Gao et al., EMNLP 2023, pp. 6465–6488](https://aclanthology.org/2023.emnlp-main.398/) | Citation-bearing generation and citation-quality evaluation. |
| `rarr` | [Gao et al., ACL 2023, pp. 16477–16508](https://aclanthology.org/2023.acl-long.910/) | Post-generation evidence attribution and revision are existing techniques. |
| `factscore` | [Min et al., EMNLP 2023, pp. 12076–12100](https://aclanthology.org/2023.emnlp-main.741/) | Atomic factual-support evaluation; our finite tuple score is not its general factuality metric. |
| `lexis` | [Atoum et al., Computers, Materials & Continua 89(2), article 50, 2026](https://www.techscience.com/cmc/v89n2/68791/html) | Structured security-report drafts from XAI evidence are close prior work. |
| `investigation` | [Eilertsen, Mavroeidis and Grov, IEEE BigData 2025, pp. 7793–7802](https://doi.org/10.1109/BigData66926.2025.11402161) | Agentic alert investigation with constrained queries; [author preprint](https://arxiv.org/abs/2604.25846) confirms the publication relationship. |
| `gsar` | [Kamelhar, arXiv:2604.23366](https://arxiv.org/abs/2604.23366) | Typed grounding and bounded recovery are adjacent prior art; preprint status is retained. |
| `revocation` | [Shen, Toyoda and Leung, arXiv:2609.08258](https://arxiv.org/abs/2609.08258) | Soft revocation labels can leave memory authoritative; no claim that our pilot replicates its benchmark. |
| `securityshap` | [Srisumrith and Sodsee, arXiv:2602.19087](https://arxiv.org/abs/2602.19087) | SHAP-based detector interpretation differs from recipient-authorized factual claim admission. |
| `refchecker` | [Hu et al., EMNLP 2024, pp. 6953–6975](https://aclanthology.org/2024.emnlp-main.395/) | Reference-based claim-triplet checking; our verifier instead uses exact finite tuples and current authorization. |
| `selfcheck` | [Manakul, Liusie and Gales, EMNLP 2023, pp. 9004–9017](https://aclanthology.org/2023.emnlp-main.557/) | Sampling consistency as a hallucination signal; consistency does not establish recipient permission. |
| `faithlm` | [Chuang et al., EACL 2026, pp. 3802–3824](https://aclanthology.org/2026.eacl-long.177/) | Intervention-based explanation faithfulness differs from fidelity to an authorized evidence snapshot. |
| `injection` | [Greshake et al., ACM AISec 2023, pp. 79–90](https://doi.org/10.1145/3605764.3623985) | Instructions inside retrieved data create indirect prompt-injection risks. The DOI registration confirms published metadata; [author preprint](https://arxiv.org/abs/2302.12173) provides open content. |
| `confidential` | [Vaswani et al., USENIX ATC 2023, pp. 501–518](https://www.usenix.org/conference/atc23/presentation/vaswani) | Hardware confidentiality and host isolation differ from ordinary local CPU execution. |
| `qwen3` | [Yang et al., Qwen3 technical report, arXiv:2505.09388](https://arxiv.org/abs/2505.09388) | Model-family identity and thinking modes; no imported performance result. |
| `offloading` | [Yuan, Han, Wang and Brinton, ACM MobiHoc 2025, pp. 201–210](https://doi.org/10.1145/3704413.3764429) | Quality/latency/cost trade-offs in local–cloud serving; our fixed local pilot does not evaluate offloading. [Author preprint](https://arxiv.org/abs/2502.11007). |

## Disposition of every supplied entry

`R01`–`R20` correspond to the numbered review references. `S01`–`S16` correspond to the separate list. Seven S entries duplicate R entries, leaving 29 distinct supplied sources. Excluded entries remain in the source audit; exclusion means they do not support a current paper claim, not that the research is invalid.

| ID | Topic or duplicate | Current disposition |
|---|---|---|
| R01 | Centrality in federated IDS | Excluded: no federated-training contribution is implemented or evaluated. |
| R02 | Federated satellite–terrestrial IDS | Excluded: different training method and deployment domain. |
| R03 | Federated heterogeneous-network IDS | Excluded: no federated-learning comparison. |
| R04 | SentinelSphere detection and awareness training | Background only: awareness training is outside both papers. |
| R05 | SHAP interpretation and sampling | Cited in Paper 2 as `securityshap`. |
| R06 | Hackphyr | Cited in Paper 2 as `hackphyr`. |
| R07 | Local–cloud offloading | Cited in Paper 2 as `offloading`; full four-author published metadata retained. |
| R08 | RedSage | Cited in Paper 2 as `redsage`. |
| R09 | Online federated streaming IDS | Excluded: no online federated-training evaluation. |
| R10 | Federated CTI for smart grids | Excluded: no federated-learning or smart-grid experiment. |
| R11 | Agentic trust coordination for federated learning | Excluded: different trust/training mechanism. |
| R12 | Privacy-preserving distributed-ML cloud architecture | Excluded: no distributed-model training contribution. |
| R13 | Attack classification and adversarial synthetic data | Excluded: protocol cases do not evaluate that classifier or generator. |
| R14 | FL-IDS transportation IoT | Excluded: no federated edge-training experiment. |
| R15 | Anomaly-detection survey | Background only. Current [arXiv:2502.13256v2](https://arxiv.org/abs/2502.13256) gives **“Cyber-Physical Systems Security: A Comprehensive Review of Anomaly Detection Techniques”**, with a 2026 *Internet of Things* publication (doi: 10.1016/j.iot.2026.101938). The supplied title/year describes the earlier manuscript; reconcile versions before reusing it. |
| R16 | Categorical robustness of ML IDS | Excluded: no categorical robustness benchmark. |
| R17 | Defense against adversarial ML IDS attacks | Excluded: adaptive adversarial detector testing remains outside the measured results. |
| R18 | Confidential computing in AI accelerator | Cited in Paper 2 as `confidential`; pasted `ijsr` artifact removed. |
| R19 | CCE serverless correlation engine | Cited in Paper 1 as `cce`; complete three-author record and pp. 95–105 replace “et al.” and pasted `ijarcce` artifact. |
| R20 | Edge-inference privacy trade-offs | Background only: architectural context does not establish this method's guarantees. |
| S01 | Duplicate of R11 | Same exclusion; no duplicate citation. |
| S02 | Google Cloud FL guide | Tutorial background only; not research evidence. |
| S03 | Duplicate of R12 | Same exclusion; no duplicate citation. |
| S04 | Medical-data exchange architecture | Excluded: medical-cloud domain and mechanism do not support the current contribution. |
| S05 | SOC 1/2/3 compliance overview | Excluded: compliance auditing is different from security-operations correlation. Page returned 403 in the recorded audit. |
| S06 | IBM cybersecurity overview | General background only; unnecessary for the technical claims. |
| S07 | Medium local-model article | Excluded as secondary commentary; direct Hackphyr/RedSage papers are cited. Page returned 403 in the recorded audit. |
| S08 | Snowflake anomaly-detection documentation | Product documentation only; the implementation does not use this service. |
| S09 | Duplicate of R15 | Same title reconciliation and background disposition. |
| S10 | Duplicate of R04 | Same background disposition. |
| S11 | Duplicate of R05 | Covered by Paper 2 `securityshap`; not counted twice. |
| S12 | Duplicate of R07 | Covered by Paper 2 `offloading`; not counted twice. |
| S13 | Duplicate of R06 | Covered by Paper 2 `hackphyr`; not counted twice. |
| S14 | Anthropic confidential inference report | Background only: this pilot has no confidential-inference implementation; R18 supplies a peer-reviewed hardware comparator. |
| S15 | Python cybersecurity tooling blog | Tutorial background only; not novelty evidence. |
| S16 | Python/Kibana platform walkthrough | Excluded as secondary implementation commentary; page returned 403 in the recorded audit. |

## Citation integrity checks

All bibliography keys must have in-text uses, all cited keys must resolve, bibliography numbering must follow first appearance, and every variant must carry the same research core and reference set. `paper-reference-register.json` records source lines and citation occurrences for review. The PDFs are rebuilt from those sources and checked for undefined citations, missing glyphs, page counts, and visual overflow. Repository measurements remain linked to their own result files in `Contribution-and-Evidence-Matrix.md`; external citations do not validate synthetic case design, real-world accuracy, or analyst usefulness.
