"""Build and time ordinary source programs through each language frontend."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCES = Path(__file__).resolve().parent
SDK = Path(r"E:\Dev\C++\VyxLan-selfhost-yolo\dist\vyx-sdk-windows-x86_64-llvm22")
MASK = (1 << 32) - 1


def lcg_reference(n: int, seed: int = 12345) -> int:
    # Independent O(log n) affine composition, used only to validate results.
    a, b, result_a, result_b = 1664525, 1013904223, 1, 0
    while n:
        if n & 1:
            result_a, result_b = a * result_a & MASK, (a * result_b + b) & MASK
        a, b = a * a & MASK, b * (a + 1) & MASK
        n >>= 1
    return (result_a * seed + result_b) & MASK


def mix_reference(n: int, seed: int = 12345) -> int:
    a, b = seed, 67890
    for _ in range(n):
        a = ((a * 1664525 + 1013904223) & MASK) ^ b
        b = ((b * 22695477 + 1) & MASK) ^ a
    return a ^ b


def execute(command: list[str], *, expected: int = 0):
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    if result.returncode != expected:
        raise RuntimeError(f"{command}\nexit={result.returncode}\n{result.stdout}{result.stderr}")
    return result


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--vyx-sdk", type=Path, default=SDK)
    parser.add_argument("--clang", default=shutil.which("clang++") or r"D:\LLVM\bin\clang++.exe")
    parser.add_argument("--rustc", default=shutil.which("rustc") or "rustc")
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--output", type=Path, default=ROOT / "target/base-runtime-benchmark")
    args = parser.parse_args()
    if args.samples < 5:
        parser.error("at least five timing samples are required")
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=True)
    compiler = args.compiler.resolve()
    vyxc = args.vyx_sdk.resolve() / "bin/vyxc.exe"
    versions = {"vyx": execute([str(vyxc), "--version"]).stdout,
                "cpp": execute([args.clang, "--version"]).stdout,
                "rust": execute([args.rustc, "-vV"]).stdout}
    report = {"measurement": "process launch to exit, including startup; shuffled sequential runs",
              "optimization": "O2; default target CPU; ordinary functions and calls; no forced noinline",
              "platform": platform.platform(), "processor": platform.processor(),
              "samples": args.samples, "warmups": 3,
              "naru_compiler_sha256": digest(compiler), "versions": versions,
              "base_rules_sha256": digest(ROOT / "dialects/base.stx"),
              "sources": str(SOURCES), "workloads": {}}
    pending = []
    for algorithm, count in (("lcg", 100000000), ("lcg", 1000000000), ("mix", 100000000)):
        name = f"{algorithm}-{count}"
        print("Building ordinary sources: " + name, flush=True)
        data = {"iterations": count, "commands": {}, "source_hashes": {}, "results": {}}
        paths = {}
        for language, suffix in (("naru", "nru"), ("vyx", "vyx"), ("cpp", "cpp"), ("rust", "rs")):
            source = work / f"{name}-{language}.{suffix}"
            source.write_text((SOURCES / f"{algorithm}.{suffix}").read_text().replace("100000000", str(count)), encoding="utf-8")
            exe = work / f"{name}-{language}.exe"
            data["source_hashes"][language] = digest(source)
            if language == "naru":
                common = [str(compiler), "build", str(source), "--rules", str(ROOT / "dialects/base.stx"),
                          "--unit", "program", "--relation", "base.emit_program", "--opt-level", "2"]
                command = [*common, "--target", "exe", "-o", str(exe), "--report", str(work / f"{name}-backend.json")]
                execute(command)
                execute([*common, "--target", "llvm-ir", "-o", str(work / f"{name}-naru.ll")])
                # The real frontend output must contain no hand-written kernel IR.
                raw = execute([str(compiler), "emit", str(source), "--rules", str(ROOT / "dialects/base.stx"),
                               "--unit", "program", "--relation", "base.emit_program"])
                (work / f"{name}-naru.mlir").write_text(raw.stdout, encoding="utf-8")
                data["naru_backend"] = json.loads((work / f"{name}-backend.json").read_text())
                optimized = (work / f"{name}-naru.ll").read_text()
                assert "phi i32" in optimized and "br i1" in optimized, "benchmark loop optimized away"
                assert not any(op in optimized for op in (" alloca ", " load ", " store ")), "scalar locals were not promoted"
            elif language == "vyx":
                command = [str(vyxc), "--src=file", str(source), "-O2", "-o", str(exe)]
                execute(command)
            elif language == "cpp":
                command = [args.clang, "-O2", "-fuse-ld=lld", str(source), "-o", str(exe)]
                execute(command)
                execute([args.clang, "-O2", "-S", "-emit-llvm", str(source), "-o", str(work / f"{name}-cpp.ll")])
            else:
                command = [args.rustc, "--crate-name", "runtime_bench", "-C", "opt-level=2", str(source), "-o", str(exe)]
                execute(command)
                execute([args.rustc, "--crate-name", "runtime_bench", "-C", "opt-level=2", "--emit=llvm-ir", str(source), "-o", str(work / f"{name}-rust.ll")])
            paths[language] = str(exe)
            data["commands"][language] = command
        print("Validating checksum against Python reference: " + name, flush=True)
        checksum = lcg_reference(count) if algorithm == "lcg" else mix_reference(count)
        data["checksum_u32"] = checksum
        for exe in paths.values():
            execute([exe], expected=checksum)
        report["workloads"][name] = data
        pending.append((name, paths, checksum))
    # All compilation and reference work finishes before timed runs begin.
    rng = random.Random(20261010)
    for name, paths, expected in pending:
        print("Timing: " + name, flush=True)
        samples = {language: [] for language in paths}
        for _ in range(3):
            for exe in paths.values():
                execute([exe], expected=expected)
        for _ in range(args.samples):
            order = list(paths)
            rng.shuffle(order)
            for language in order:
                start = time.perf_counter_ns()
                execute([paths[language]], expected=expected)
                samples[language].append((time.perf_counter_ns() - start) / 1e6)
        for language, values in samples.items():
            result = {"median_ms": statistics.median(values), "min_ms": min(values), "max_ms": max(values),
                      "p90_ms": sorted(values)[math.ceil(len(values) * .9) - 1],
                      "mean_ms": statistics.mean(values), "samples_ms": values}
            report["workloads"][name]["results"][language] = result
            print(f"  {language}: {result['median_ms']:.3f} ms", flush=True)
        (work / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("Report: " + str(work / "results.json"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
