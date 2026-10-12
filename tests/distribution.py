"""Run a relocated distribution without external tools or child processes."""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile

from native_process import execute

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--package", type=Path, required=True)
args = parser.parse_args()
package = args.package.resolve()
compiler = package / "naru.exe"
metadata = json.loads((package / "naru-distribution.json").read_text(encoding="utf-8-sig"))
assert metadata["external_toolchain_required"] is False
assert (package / "docs" / "rule-system.md").is_file()
assert (package / "docs" / "projects.md").is_file()
assert (package / "docs" / "operators.md").is_file()
assert (package / "Naru.lock").is_file()
assert not (package / "examples/ffi/target").exists(), "Distribution included example build artifacts"
environment = dict(os.environ, PATH="")
environment.pop("NARU_MLIR_BACKEND", None)


def run(*options, cwd, expected=0):
    result = execute([str(compiler), *map(str, options)], cwd=cwd, env=environment)
    assert result.returncode == expected, result.stdout + result.stderr
    return result


with tempfile.TemporaryDirectory(prefix="naru standalone consumer ") as folder:
    work = Path(folder)
    answer = work / "answer.exe"
    run("build", "--project", package / "Naru.toml", "--locked", "--target", "exe", "-o", answer, cwd=work)
    assert execute([str(answer)], cwd=work, env=environment).returncode == 42
    print("PASS relocated project compiles and executes without tools or child processes")
    ffi = work / "ffi.exe"
    run("build", "--project", package / "examples/ffi", "--locked", "-o", ffi, cwd=work)
    actual = execute([str(ffi)], cwd=work, env=environment)
    assert actual.returncode == 42 and actual.stdout.strip() == "Naru: project dialects and automatic C linking", actual
    print("PASS relocated project references and automatic CRT linking with an unchanged lock")
    money = work / "money.mlir"
    run("build", package / "examples/money.nru", "--rules", package / "dialects/money.stx",
        "--unit", "program", "--relation", "emit_program", "-o", money, cwd=work)
    assert "arith.addi" in money.read_text()
    print("PASS relocated distribution includes the extensible numeric type libraries")
    operators = work / "operators.exe"
    run("build", package / "examples/operators.nru", "--rules", package / "dialects/standard.stx",
        "--unit", "program", "--relation", "standard.emit_program", "--target", "exe", "-o", operators, cwd=work)
    assert execute([str(operators)], cwd=work, env=environment).returncode == 42
    print("PASS relocated user operator declarations and composed standard rules")
    device = work / "device.mlir"
    run("build", package / "examples/device.nru", "--rules", package / "dialects/custom_device.stx",
        "--target", package / "backend/device-target.json", "-o", device, cwd=work)
    assert "naru_device.launch" in device.read_text()
    print("PASS relocated IRDL target and rule paths")
    native = work / "native-device.mlir"
    run("build", package / "examples/native_device.nru", "--rules", package / "dialects/native_device.stx",
        "--dialect-plugin", package / "plugins/naru_device_plugin.dll", "-o", native, cwd=work)
    assert "naru_native.launch" in native.read_text()
    print("PASS relocated native dialect plugin")
    mark = work / "marked.mlir"
    run("build", package / "examples/answer.nru", "--rules", package / "dialects/base.stx",
        "--pass-plugin", package / "plugins/naru_mark_plugin.dll",
        "--pass-pipeline", "builtin.module(naru-test-mark,canonicalize,cse)", "-o", mark, cwd=work)
    assert 'naru.test_pass = "executed"' in mark.read_text()
    print("PASS relocated native pass plugin")
print("7/7 distribution checks passed")
