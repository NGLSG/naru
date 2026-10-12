#!/usr/bin/env python3
"""Compile .nru through rules and real MLIR; verify CPU and custom-dialect paths."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import os
import subprocess
import sys
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "target" / "naru.exe"


def run(arguments: list[str], *, expected: int = 0) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ, PATH="")
    result = execute(arguments, cwd=ROOT, env=environment)
    if result.returncode != expected:
        raise AssertionError(
            f"expected exit {expected}, got {result.returncode}: {arguments!r}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def emit(compiler: Path, source: str, destination: Path, *rules: str) -> None:
    arguments = [str(compiler), "emit", source, "-o", str(destination)]
    for rule in rules:
        arguments.extend(("--rules", rule))
    if "dialects/custom_device.stx" in rules:
        arguments.extend(("--irdl", str(ROOT / "backend/examples/device.irdl.mlir")))
    run(arguments)
    if not destination.is_file():
        raise AssertionError(f"frontend did not write {destination}")


def backend(source: Path, output: Path, target: str, *extra: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
    return run([str(COMPILER), "opt", str(source), "--output", str(output),
                "--target", target, *extra], expected=expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target" / "naru.exe")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    global COMPILER
    COMPILER = compiler
    if not compiler.is_file():
        parser.error(f"compiler does not exist: {compiler}")
    passed = 0
    try:
        # Spaces in the output path are intentional: all process calls use argv.
        with tempfile.TemporaryDirectory(prefix="naru e2e ") as directory:
            work = Path(directory)
            answer = work / "answer.mlir"
            alternate = work / "alternate.mlir"
            emit(compiler, "examples/answer.nru", answer, "dialects/base.stx")
            emit(compiler, "examples/alternate.nru", alternate, "dialects/base.stx", "dialects/alternate.stx")
            assert answer.read_text(encoding="utf-8") == alternate.read_text(encoding="utf-8"), \
                "fn and def should share their semantic tree and emitted operations"
            print("PASS distinct source grammars produce identical MLIR")
            passed += 1

            optimized = work / "answer.optimized.mlir"
            backend(answer, optimized, "mlir")
            text = optimized.read_text(encoding="utf-8")
            assert re.search(r"arith\.constant\s+42\s*:\s*i32", text), text
            assert "arith.addi" not in text and "arith.muli" not in text, text
            print("PASS MLIR verifies and folds 2 + 8 * 5 to a single constant")
            passed += 1

            for level in ("0", "3"):
                executable = work / f"answer.O{level}.exe"
                extra = ["--opt-level", level]
                if level == "0":
                    extra.extend(("--pass-pipeline", "builtin.module()"))
                backend(answer, executable, "exe", *extra)
                run([str(executable)], expected=42)
                print(f"PASS native O{level} program exits with 42")
                passed += 1

            device = work / "device.mlir"
            emitted = work / "device.verified.mlir"
            emit(compiler, "examples/device.nru", device, "dialects/custom_device.stx")
            backend(device, emitted, "backend/device-target.json")
            text = emitted.read_text(encoding="utf-8")
            assert '"naru_device.launch"' in text and "workgroups = 8 : i32" in text, text
            assert "llvm." not in text, text
            print("PASS custom IRDL dialect is verified without LLVM lowering")
            passed += 1

            # Registered dialects are mandatory; accepting unknown operations
            # would hide incorrect definitions and provide no useful verification.
            result = backend(device, work / "unregistered.mlir", "mlir", expected=1)
            assert "naru_device" in result.stdout + result.stderr, result.stdout + result.stderr
            print("PASS missing custom dialect registration is diagnosed")
            passed += 1
    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
        print(f"FAIL after {passed} passed checks\n{error}", file=sys.stderr)
        return 1
    print(f"\n{passed}/{passed} frontend/backend integration checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
