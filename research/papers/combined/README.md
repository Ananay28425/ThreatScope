# Combined research manuscript

**ThreatScope: Bounded Evidence Sharing, Threat Correlation, and Grounded Local AI**

This manuscript combines the former framework and local interpretation research papers. It follows evidence through disclosure, correlation, authorization and report validation. The GTSS 2027 manuscript is a separately preserved exception.

`core.tex` is the authoritative argument. `extension-8.tex`, `extension-10.tex` and `extension-12.tex` retain additional method, failure and reproducibility analysis. The `combined-*pages.tex` files expand the core and bibliography into standalone editable LaTeX documents suitable for the built-in editor.

Every variant cites the same 30 references. `Reference-and-Claim-Map.md` and `reference-map.json` trace those entries to their supported claims. A standard or official dataset record is identified as such. Related preprints retain preprint status; verified published versions control the bibliography when available.

The two existing studies retain their own denominators. The manuscript reports synthetic protocol results and a separate eight-case CPU pilot, including the negative finding that all complete-method explanations used fallback. It does not claim integrated field accuracy, human usefulness or formal differential privacy.

Run `python generate_variants.py` after editing the core or extensions. For a local build, use XeLaTeX or Tectonic with IEEEtran and fontspec installed. The generated files contain editable vector diagram definitions and bibliography entries. Compile each standalone file and verify its page count after edits. Final PDFs must also be rendered and inspected.

Before submission, check the selected venue's page limit, anonymity requirements and overlap with GTSS. These four versions are one paper. No venue submission or public release is performed by preparing them.
