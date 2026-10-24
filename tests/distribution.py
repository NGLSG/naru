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
assert metadata['license'] == 'MIT OR Apache-2.0'
assert (package/'LICENSE-MIT').is_file() and (package/'LICENSE-APACHE').is_file()
assert (package/'SHA256SUMS').is_file()
assert (package / "docs" / "rule-system.md").is_file()
assert (package / "docs" / "projects.md").is_file()
assert (package / "docs" / "operators.md").is_file()
assert (package / 'docs/c11-conformance.md').is_file()
assert (package / 'docs/coro.md').is_file()
assert (package / metadata['coro']['runtime']).is_file()
assert (package / 'runtime/coro/tasks.h').is_file()
assert metadata['c11']['full_conformance_claimed'] is False
assert (package / metadata['c11']['support_plan']).is_file()
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
    coroutine = work / 'coroutine.exe'
    run('build', '--project', package / 'examples/coro', '--locked', '-o', coroutine, cwd=work)
    assert execute([str(coroutine)], cwd=work, env=environment).returncode == 42
    print('PASS relocated coroutine rules and target pass compile and execute without tools')
    asynchronous = work / 'async.exe'
    run('build', '--project', package / 'examples/async', '--locked', '-o', asynchronous, cwd=work)
    assert execute([str(asynchronous)], cwd=work, env=environment).returncode == 42
    print('PASS relocated asynchronous project links its packaged executor without tools')
    storage_source = work / "storage.c"
    storage_source.write_text('int answer(register int n){register int *p=&n;return *p;}\n', encoding="utf-8")
    # A register parameter itself cannot have its address taken. Verify that
    # the packaged extension diagnoses this before publishing an output.
    storage = work / "storage.exe"
    storage.write_bytes(b"previous-success")
    failed = run("build", storage_source, "--rules", package / "dialects/c11.stx",
        "--frontend", "c11.frontend", "--entry", "c11.item", "--unit", "program",
        "--relation", "c11.emit_program", "--runtime", "crt-static", "--target", "exe",
        "-o", storage, cwd=work, expected=1)
    assert "address of a C register object" in failed.stderr + failed.stdout, failed.stderr + failed.stdout
    assert storage.read_bytes() == b"previous-success"
    storage_source.write_text('int answer(register int n){return n;}int main(void){auto int n=42;register int *p=&n;return answer(*p);}\n', encoding="utf-8")
    run("build", storage_source, "--rules", package / "dialects/c11.stx",
        "--frontend", "c11.frontend", "--entry", "c11.item", "--unit", "program",
        "--relation", "c11.emit_program", "--runtime", "crt-static", "--target", "exe",
        "-o", storage, cwd=work)
    assert execute([str(storage)], cwd=work, env=environment).returncode == 42
    print("PASS relocated C11 storage module compiles and preserves required diagnostics")
    basic = work/'basic.exe'
    run('build', '--project', package/'examples/basic', '--locked', '--target', 'exe', '-o', basic, cwd=work)
    basic_result = execute([str(basic)], cwd=work, env=environment)
    assert basic_result.returncode == 0 and basic_result.stdout.strip() == '55', basic_result
    colon = work/'colon.bas'
    colon.write_text('10 LET X = 1 : PRINT X\n20 END\n', encoding='utf-8')
    basic.write_bytes(b'previous-success')
    rejected = run('build', colon, '--rules', package/'dialects/basic.stx', '--frontend', 'basic.frontend',
                   '--unit', 'program', '--relation', 'base.emit_program', '--runtime', 'crt-static',
                   '--target', 'exe', '-o', basic, cwd=work, expected=1)
    assert 'colon-separated statements are not yet supported' in rejected.stderr + rejected.stdout
    assert basic.read_bytes() == b'previous-success'
    print('PASS relocated BASIC project compiles and executes its archived language example')
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
print("11/11 distribution checks passed")
