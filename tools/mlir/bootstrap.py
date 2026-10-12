"""Install the pinned Windows MLIR tools locally, without changing PATH.

The archive is published by llvm/eudsl and verified against its release digest.
Python 3.11+; no third-party dependencies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / ".tools" / "mlir"
NAME = "mlir_windows_amd64_20261009+19d3b2d28.tar.gz"
URL = "https://github.com/llvm/eudsl/releases/download/llvm/" + NAME
SHA256 = "a14f88bb2bb099505df1b01a06d02935807d5c325e7fa6394a5de8b5febfb6be"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use an already downloaded archive")
    args = parser.parse_args()
    HOME.mkdir(parents=True, exist_ok=True)
    archive = args.archive or HOME / NAME
    if not archive.is_file():
        partial = archive.with_suffix(archive.suffix + ".partial")
        print(f"Downloading {URL}", flush=True)
        with urllib.request.urlopen(URL, timeout=60) as source, partial.open("wb") as target:
            shutil.copyfileobj(source, target)
        partial.replace(archive)
    actual = digest(archive)
    if actual != SHA256:
        raise SystemExit(f"SHA256 mismatch: expected {SHA256}, got {actual}: {archive}")
    destination = HOME / "toolchain"
    destination.mkdir(exist_ok=True)
    resolved = destination.resolve()
    print(f"Verified SHA256; extracting to {destination}", flush=True)
    with tarfile.open(archive, "r:gz") as source:
        # Reject archives containing links or entries outside the install root.
        for member in source:
            target = (destination / member.name).resolve()
            if not target.is_relative_to(resolved) or member.issym() or member.islnk():
                raise SystemExit(f"Unsafe archive entry: {member.name}")
            if not member.isfile() and not member.isdir():
                raise SystemExit(f"Unsupported archive entry: {member.name}")
            source.extract(member, destination)
    candidates = list(destination.rglob("mlir-opt.exe"))
    if len(candidates) != 1:
        raise SystemExit(f"Expected one mlir-opt.exe, found {len(candidates)}")
    info = {
        "source": URL,
        "sha256": SHA256,
        "llvm_revision": "19d3b2d28",
        "bin": str(candidates[0].parent.relative_to(HOME)),
    }
    (HOME / "toolchain.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    print(candidates[0])


if __name__ == "__main__":
    main()
