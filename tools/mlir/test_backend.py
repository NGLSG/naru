"""Integration checks against Naru's embedded MLIR/LLVM/LLD libraries."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests"))
from native_process import execute
EXAMPLES = ROOT / "backend" / "examples"
COMPILER = ROOT / "target" / "naru.exe"


def invoke(source: Path, output: Path, *options: str, success: bool = True) -> subprocess.CompletedProcess:
    command = [str(COMPILER), "opt", str(source), "--output", str(output), *options]
    result = execute(command, cwd=ROOT, env=dict(os.environ, PATH=""))
    # Frontend diagnostics share the command's output stream.
    result.stderr = result.stdout + result.stderr
    if (result.returncode == 0) != success:
        raise AssertionError(f"Unexpected exit {result.returncode}: {command}\n{result.stdout}\n{result.stderr}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--filter", help="Run only checks containing this name")
    args = parser.parse_args()
    version = execute([str(COMPILER), "--version"], cwd=ROOT).stdout.strip()
    results = []

    def check(name, test):
        if args.filter and args.filter not in name:
            return
        start = time.perf_counter()
        try:
            detail = test()
            results.append({"test": name, "passed": True, "detail": detail, "seconds": round(time.perf_counter() - start, 4)})
            print("PASS " + name)
        except Exception as error:
            results.append({"test": name, "passed": False, "error": str(error)})
            print("FAIL " + name + ": " + str(error), file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="naru backend tests ") as directory:
        work = Path(directory)

        def constant_fold():
            output = work / "folded.mlir"
            invoke(EXAMPLES / "fold.mlir", output)
            text = output.read_text()
            assert "arith.constant 42 : i32" in text and "arith.addi" not in text, text
            return "20 + 22 folds to one i32 constant 42"

        def cpu():
            output = work / "answer.exe"
            invoke(EXAMPLES / "fold.mlir", output, "--target", "exe")
            result = execute([str(output)], cwd=work, timeout=10)
            assert result.returncode == 42, result.returncode
            return "Embedded MLIR -> LLVM -> TargetMachine -> LLD executable exits 42 under a no-child-process Job"

        def fusion():
            output = work / "fusion.mlir"
            invoke(EXAMPLES / "fusion.mlir", output, "--target", str(ROOT / "backend" / "fusion-target.json"))
            text = output.read_text()
            assert text.count("affine.for") == 1, text
            assert "memref.alloc" not in text and "memref.dealloc" not in text, text
            assert text.count("affine.load") == 1 and text.count("affine.store") == 1, text
            return "2 loops -> 1; temporary allocation, deallocation, load and store eliminated"

        def custom_dialect():
            output = work / "device.mlir"
            invoke(EXAMPLES / "device.mlir", output, "--target", str(ROOT / "backend" / "device-target.json"))
            text = output.read_text()
            assert "naru_device.activate" in text and "!naru_device.tile<f32>" in text, text
            assert "llvm." not in text, text
            return "Registered IRDL operations and custom f32 tile type preserved in a non-LLVM artifact"

        def custom_type_error():
            output = work / "protected.mlir"
            output.write_text("existing-good-artifact")
            result = invoke(EXAMPLES / "device-invalid.mlir", output, "--target", str(ROOT / "backend" / "device-target.json"), success=False)
            assert "expected base type 'naru_device.tile' but got 'i32'" in result.stderr, result.stderr
            assert output.read_text() == "existing-good-artifact"
            return "IRDL verifier rejects wrong operand type; existing output is not replaced"

        def unregistered():
            output = work / "unregistered.mlir"
            result = invoke(EXAMPLES / "device.mlir", output, success=False)
            assert not output.exists()
            assert "naru_device" in result.stderr
            return "Device program is rejected without its dialect registration"

        def unknown_pass():
            output = work / "unknown-pass.mlir"
            invoke(EXAMPLES / "fold.mlir", output, "--pass-pipeline", "builtin.module(naru-no-such-pass)", success=False)
            assert not output.exists()
            return "Unknown pass cannot silently fall back to an unoptimized build"

        def launch():
            source = work / "launch.mlir"
            source.write_text('module { "naru_device.launch"() {workgroups = 4 : i32} : () -> () }')
            output = work / "launch-out.mlir"
            invoke(source, output, "--target", str(ROOT / "backend" / "device-target.json"))
            assert "workgroups = 4 : i32" in output.read_text()
            source.write_text('module { "naru_device.launch"() {workgroups = "invalid"} : () -> () }')
            result = invoke(source, work / "bad-launch.mlir", "--target", str(ROOT / "backend" / "device-target.json"), success=False)
            assert "builtin.integer" in result.stderr, result.stderr
            return "Device workgroups IntegerAttr is accepted; a string attribute is rejected"

        def path_protection():
            source = work / "protected-source.mlir"
            shutil.copy2(EXAMPLES / "fold.mlir", source)
            irdl = work / "protected-dialect.mlir"
            shutil.copy2(EXAMPLES / "device.irdl.mlir", irdl)
            profile = work / "protected-target.json"
            profile.write_text(json.dumps({"irdl": [str(irdl)]}))
            output = work / "protected-output.mlir"
            output.write_text("prior-successful-artifact")
            plugin = work / "protected-plugin.dll"
            plugin.write_bytes(b"This sentinel must be protected before attempting to load a plugin.")
            expected = {path: path.read_bytes() for path in (source, irdl, profile, output, plugin)}
            configurations = [
                (output, ["--report", str(source)]),
                (output, ["--report", str(output)]),
                (profile, ["--target", str(profile)]),
                (irdl, ["--irdl", str(irdl)]),
                (output, ["--target", str(profile), "--report", str(profile)]),
                (output, ["--irdl", str(irdl), "--report", str(irdl)]),
                (plugin, ["--pass-plugin", str(plugin)]),
                (output, ["--dialect-plugin", str(plugin), "--report", str(plugin)]),
            ]
            alias = work / "hardlink-source.mlir"
            os.link(source, alias)
            configurations.append((output, ["--report", str(alias)]))
            for destination, options in configurations:
                result = invoke(source, destination, *options, success=False)
                assert "overwrite" in result.stderr or "must be different files" in result.stderr, result.stderr
                for path, original in expected.items():
                    assert path.read_bytes() == original, f"Protected file changed: {path} for {options}"
            return "9 output/report input collisions rejected, including target, IRDL, plugins and a hard-linked report path"

        check("constant-folding", constant_fold)
        check("cpu-aot", cpu)
        check("affine-fusion", fusion)
        check("custom-dialect-non-llvm", custom_dialect)
        check("custom-dialect-type-error", custom_type_error)
        check("unregistered-dialect-error", unregistered)
        check("unknown-pass-error", unknown_pass)
        check("custom-dialect-attribute-validation", launch)
        check("path-protection", path_protection)

    if not results:
        parser.error("No checks matched --filter")
    report = {"mlir_version": version, "tests": results, "passed": all(item["passed"] for item in results)}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(item['passed'] for item in results)}/{len(results)} backend checks passed")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
