"""Regenerate standalone manuscript variants from this folder's editable sources."""
from __future__ import annotations

import json
import re
from pathlib import Path


def main() -> None:
    """Expand substantive sections, diagrams and the cited bibliography."""
    root = Path(__file__).resolve().parent
    core = (root / "core.tex").read_text(encoding="utf-8")
    references = {r["key"]: r for r in json.loads((root / "reference-map.json").read_text(encoding="utf-8"))["references"]}
    order = list(dict.fromkeys(k.strip() for call in re.finditer(r"\\cite\{([^}]+)\}", core) for k in call.group(1).split(",")))
    if len(references) != 30 or set(order) != set(references):
        raise ValueError("The core must cite all 30 registered references, with no unknown keys.")
    bibliography = "\\begin{thebibliography}{30}\n" + "\n".join("\\bibitem{" + k + "} " + references[k]["ieee_reference"] for k in order) + "\n\\end{thebibliography}\n"
    extensions = {n: (root / f"extension-{n}.tex").read_text(encoding="utf-8") for n in (8, 10, 12)}
    diagrams = "\n\n".join(re.findall(r"\\begin\{figure\}\[t\].*?\\end\{figure\}", extensions[8], re.S))
    for length in (6, 8, 10, 12):
        text = "\\def\\PaperLength{" + str(length) + "}\n" + core.replace("% BIBLIOGRAPHY", bibliography)
        text = text.replace("% DIAGRAMS_6", diagrams if length == 6 else "")
        for cutoff, extension in extensions.items():
            text = text.replace(f"% EXTENSION_{cutoff}", extension if length >= cutoff else "")
        labels = re.findall(r"\\label\{([^}]+)\}", text)
        if len(labels) != len(set(labels)) or not set(re.findall(r"\\ref\{([^}]+)\}", text)) <= set(labels):
            raise ValueError(f"Variant {length} has duplicate or unresolved labels.")
        (root / f"combined-{length}pages.tex").write_text(text, encoding="utf-8")
    print("Generated four editable variants. Compile and verify page counts after content edits.")


if __name__ == "__main__":
    main()
