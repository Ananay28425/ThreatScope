"""Download pinned official inference artifacts; keep weights and executable caches outside Git."""
import argparse
import hashlib
import json
import platform
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
SOURCES = {
    "small": ("Qwen/Qwen3-1.7B-GGUF", "90862c4b9d2787eaed51d12237eafdfe7c5f6077", "Qwen3-1.7B-Q8_0.gguf"),
    "large": ("Qwen/Qwen3-4B-GGUF", "bc640142c66e1fdd12af0bd68f40445458f3869b", "Qwen3-4B-Q4_K_M.gguf"),
}
LLAMA_TAG = "b11256"


def sha256(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def fetch(url, path, expected_hash=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and (expected_hash is None or sha256(path) == expected_hash):
        return
    temporary = path.with_suffix(path.suffix + ".partial")
    print(f"Downloading {path.name}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "ThreatScope-reproducibility/0.2"})
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
        while data := response.read(1024 * 1024):
            output.write(data)
    if expected_hash and sha256(temporary) != expected_hash:
        raise RuntimeError("download_digest_mismatch")
    temporary.replace(path)


def json_url(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={
        "User-Agent": "ThreatScope-reproducibility/0.2"
    }), timeout=60) as response:
        return json.load(response)


def setup(selected):
    if platform.system() != "Windows":
        raise RuntimeError("This bootstrap targets Windows; use the pinned llama.cpp release on other hosts.")
    release = json_url(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{LLAMA_TAG}")
    asset = next(a for a in release["assets"] if a["name"] == f"llama-{LLAMA_TAG}-bin-win-cpu-x64.zip")
    archive = RUNTIME / asset["name"]
    expected = (asset.get("digest") or "").removeprefix("sha256:") or None
    fetch(asset["browser_download_url"], archive, expected)
    binary_dir = RUNTIME / "llama"
    binary_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            target = (binary_dir / name).resolve()
            if not target.is_relative_to(binary_dir.resolve()):
                raise RuntimeError("unsafe_archive_path")
        bundle.extractall(binary_dir)
    quantizer = next(binary_dir.rglob("llama-quantize.exe"))
    manifest = {"runtime": {"tag": LLAMA_TAG, "asset": asset["name"], "sha256": sha256(archive)}, "models": []}
    for label in selected:
        repo, revision, name = SOURCES[label]
        metadata = json_url(f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true")
        record = next(s for s in metadata["siblings"] if s["rfilename"] == name)
        upstream_hash = record["lfs"]["sha256"]
        source = RUNTIME / "models" / name
        fetch(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", source, upstream_hash)
        deployed = source
        if label == "small":
            deployed = source.with_name("Qwen3-1.7B-Q4_K_M.gguf")
            if not deployed.exists() or deployed.stat().st_size < 500_000_000:
                temporary = deployed.with_suffix(".partial.gguf")
                subprocess.run(
                    [str(quantizer), "--allow-requantize", str(source), str(temporary), "Q4_K_M"],
                    check=True,
                )
                temporary.replace(deployed)
        manifest["models"].append({
            "name": label, "repository": repo, "revision": revision, "source_file": name,
            "source_sha256": upstream_hash, "file": deployed.name, "sha256": sha256(deployed),
            "quantization": "Q4_K_M", "derived_from_q8": label == "small",
        })
    target = ROOT / "research" / "models.lock.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("Pinned artifacts verified; model manifest saved.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", choices=["small", "large"], default=["small", "large"])
    setup(parser.parse_args().models)
