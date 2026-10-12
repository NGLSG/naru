"""Prepare a local Windows import overlay without modifying the MLIR SDK."""
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--llvm-root", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
relative = Path("mlir/Support/TypeID.h")
text = (args.llvm_root / "include" / relative).read_text()
needle = "static SelfOwningTypeID id;"
if text.count(needle) != 1:
    raise RuntimeError("Unexpected MLIR TypeID header; update the plugin overlay for this version")
text = text.replace(needle, "static NARU_MLIR_TYPEID_IMPORT SelfOwningTypeID id;")
text = "#define NARU_MLIR_PLUGIN_HEADERS 1\n#ifndef NARU_MLIR_TYPEID_IMPORT\n#define NARU_MLIR_TYPEID_IMPORT\n#endif\n" + text
destination = args.output / relative
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(text, encoding="utf-8")
