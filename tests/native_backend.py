"""Verify the native compiler under a Job that forbids child processes."""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
COMPILER = ROOT / "target/naru.exe"


def invoke(*options: str, expected: int = 0, cwd: Path = ROOT, compiler: Path = COMPILER):
    result = execute([str(compiler), *map(str, options)], cwd=cwd, env=dict(os.environ, PATH=""))
    assert result.returncode == expected, f"exit={result.returncode}, expected={expected}\n{result.stdout}{result.stderr}"
    return result.stdout + result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--frozen-cfg", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "tests/native-verification.json")
    args = parser.parse_args()
    results = []

    def check(name, test):
        try:
            test()
            results.append({"test": name, "passed": True})
            print("PASS " + name)
        except (AssertionError, OSError, subprocess.TimeoutExpired) as problem:
            results.append({"test": name, "passed": False, "error": str(problem)})
            print("FAIL " + name + ": " + str(problem), file=sys.stderr)

    with tempfile.TemporaryDirectory(prefix="naru native acceptance ") as folder:
        work = Path(folder)
        source = ROOT / "examples/answer.nru"
        base = ROOT / "dialects/base.stx"

        def target(kind, suffix):
            out = work / ("answer." + suffix)
            report = out.with_suffix(".json")
            invoke("build", source, "--rules", base, "--target", kind, "-o", out, "--report", report)
            info = json.loads(report.read_text())
            assert info["backend"] == "in-process" and info["processes_spawned"] == 0 and info["success"], info
            if kind == "bytecode":
                assert out.read_bytes().startswith(b"ML\xefR"), out.read_bytes()[:8]
            elif kind == "object":
                assert out.read_bytes()[:2] == b"\x64\x86", "expected AMD64 COFF"
            elif kind == "llvm-ir":
                assert "ret i32 42" in out.read_text(), out.read_text()
            elif kind == "exe":
                result = execute([str(out)], cwd=work, env=dict(os.environ, PATH=""))
                assert result.returncode == 42, result

        for kind, suffix in (("bytecode", "mlirbc"), ("object", "obj"), ("llvm-ir", "ll"), ("exe", "exe")):
            check("no child processes or PATH: " + kind, lambda kind=kind, suffix=suffix: target(kind, suffix))

        def loop(level):
            out = work / ("loop-O" + level + ".exe")
            invoke("build", ROOT / "tests/fixtures/raw_cfg.nru", "--rules", ROOT / "dialects/control_flow.stx",
                   "--target", "exe", "--opt-level", level, "--pass-pipeline", "builtin.module()", "-o", out)
            assert execute([str(out)], cwd=work).returncode == 42

        for level in ("0", "3"):
            check("CFG arguments and backedge at O" + level, lambda level=level: loop(level))

        def size(level):
            out = work / ("size-" + level + ".ll")
            invoke("build", source, "--rules", base, "--target", "llvm-ir", "--opt-level", level, "-o", out)
            ir = out.read_text()
            assert "optsize" in ir and (level != "z" or "minsize" in ir), ir
        for level in ("s", "z"):
            check("LLVM size preference O" + level, lambda level=level: size(level))

        def dll_symbols():
            program=work/'dll-symbols.mlir'
            program.write_text('''module {
              llvm.func @answer() -> i32 attributes {naru.llvm.dll_storage_class = "export"} {
                %0 = llvm.call @foreign() : () -> i32
                llvm.return %0 : i32
              }
              llvm.func @foreign() -> i32 attributes {naru.llvm.dll_storage_class = "import"}
              llvm.mlir.global external @exported_value(0 : i32) {naru.llvm.dll_storage_class = "export"} : i32
            }''')
            for level in ('0','2'):
                out=work/('dll-O'+level+'.ll')
                invoke('opt',program,'--target','llvm-ir','--opt-level',level,'--pass-pipeline','builtin.module()','-o',out)
                ir=out.read_text()
                assert 'define dllexport' in ir and '@answer()' in ir,ir
                assert 'declare dllimport' in ir and '@foreign()' in ir,ir
                assert re.search(r'@exported_value = dllexport .*\bglobal\b',ir),ir
            obj=work/'dll.obj'
            invoke('opt',program,'--target','object','--opt-level','2','--pass-pipeline','builtin.module()','-o',obj)
            assert b'/EXPORT:answer' in obj.read_bytes() and b'/EXPORT:exported_value' in obj.read_bytes(),obj.read_bytes()
        check('generic DLL symbol facts survive optimization and emit COFF export directives',dll_symbols)

        def initializer_result(body, contains=None):
            program = work / 'initializer.mlir'
            program.write_text('''module {
              llvm.mlir.global external @number(42 : i32) : i32
              llvm.func @foreign() -> i64
              llvm.mlir.global external @image() : i64 {
            ''' + body + '\n}}')
            for level in ('0', '2'):
                output = work / ('initializer-O' + level + '.ll')
                output.write_bytes(b'previous-success')
                diagnostic = invoke('opt', program, '--target', 'llvm-ir', '--opt-level', level,
                    '--pass-pipeline', 'builtin.module()', '-o', output, expected=1 if contains else 0)
                if contains:
                    assert contains in diagnostic, diagnostic
                    assert output.read_bytes() == b'previous-success', 'failed initializer replaced the artifact'
                else:
                    assert 'ptrtoint (ptr @number to i64)' in output.read_text(), output.read_text()

        pointer_constant = '''
          %p = llvm.mlir.addressof @number : !llvm.ptr
          %i = llvm.ptrtoint %p : !llvm.ptr to i64
        '''
        check('global pointer relocations remain LLVM constants', lambda: initializer_result(
            pointer_constant + 'llvm.return %i : i64'))
        check('nonconstant symbolic shifts diagnose without LLVM destruction aborts', lambda: initializer_result(
            pointer_constant + '''%one = llvm.mlir.constant(1 : i64) : i64
              %shift = llvm.lshr %i, %one : i64
              llvm.return %shift : i64''', 'global initializer did not lower to an LLVM constant'))
        check('side-effecting global calls preserve verifier diagnostics and the artifact', lambda: initializer_result(
            '%call = llvm.call @foreign() : () -> i64\nllvm.return %call : i64',
            'ops with side effects not allowed in global initializers'))
        check('zero-result global stores diagnose before LLVM translation', lambda: initializer_result(
            pointer_constant + '''%value = llvm.mlir.constant(42 : i32) : i32
              llvm.store %value, %p : i32, !llvm.ptr
              llvm.return %i : i64''', 'ops with side effects not allowed in global initializers'))

        def invalid_dll_fact(attributes,definition=True,triple=None,contains=''):
            program=work/'invalid-dll.mlir'
            program.write_text('module { llvm.func @answer() -> i32 attributes {'+attributes+'}'+
                (' { %0 = llvm.mlir.constant(42 : i32) : i32 llvm.return %0 : i32 }' if definition else '')+' }')
            out=work/'protected-dll.ll';out.write_text('previous-success')
            diagnostic=invoke('opt',program,'--target','llvm-ir','--pass-pipeline','builtin.module()','-o',out,
                *(['--triple',triple] if triple else []),expected=1)
            assert contains in diagnostic and out.read_text()=='previous-success',diagnostic
        check('DLL storage cannot annotate definitions as imported',lambda: invalid_dll_fact(
            'naru.llvm.dll_storage_class = "import"',contains='imports must be declarations'))
        check('DLL storage requires a recognized string value',lambda: invalid_dll_fact(
            'naru.llvm.dll_storage_class = "unknown"',contains='must be export or import'))
        check('DLL storage rejects non-string facts',lambda: invalid_dll_fact(
            'naru.llvm.dll_storage_class = 1 : i32',contains='requires a string'))
        check('Windows DLL facts reject a non-Windows target',lambda: invalid_dll_fact(
            'naru.llvm.dll_storage_class = "export"',triple='x86_64-unknown-linux-gnu',contains='Windows external symbol'))

        def native_pass():
            out = work / "pass.mlir"
            invoke("build", source, "--rules", base, "--pass-plugin", ROOT / "target/naru_mark_plugin.dll",
                   "--pass-pipeline", "builtin.module(naru-test-mark,canonicalize,cse)", "-o", out)
            text = out.read_text()
            assert 'naru.test_pass = "executed"' in text and "arith.constant 42" in text, text
        check("native pass plugin shares host TypeIDs and registry", native_pass)

        def native_dialect():
            out = work / "native-device.mlir"
            invoke("build", ROOT / "examples/native_device.nru", "--rules", ROOT / "dialects/native_device.stx",
                   "--dialect-plugin", ROOT / "target/naru_device_plugin.dll", "-o", out)
            assert "naru_native.launch" in out.read_text() and "workgroups = 8" in out.read_text()
            invalid = work / "bad-native.nru"
            invalid.write_text("native_device 0\n")
            prior = out.read_bytes()
            diagnostic = invoke("build", invalid, "--rules", ROOT / "dialects/native_device.stx",
                   "--dialect-plugin", ROOT / "target/naru_device_plugin.dll", "-o", out, expected=1)
            assert "positive integer workgroups" in diagnostic, diagnostic
            assert out.read_bytes() == prior
        check("native dialect registration and verifier", native_dialect)

        def repeated_extensions():
            irdl = work / "device.irdl.mlir"
            irdl.write_bytes((ROOT / "backend/examples/device.irdl.mlir").read_bytes())
            alias = work / "same-definition.mlir"
            os.link(irdl, alias)
            profile = work / "device-target.json"
            profile.write_text(json.dumps({"irdl": [irdl.name]}))
            out = work / "repeated-irdl.mlir"
            invoke("build", ROOT / "examples/device.nru", "--rules", ROOT / "dialects/custom_device.stx",
                   "--target", profile, "--irdl", irdl, "--irdl", alias, "-o", out)
            assert "naru_device.launch" in out.read_text()
            plugin = ROOT / "target/naru_mark_plugin.dll"
            invoke("build", source, "--rules", base, "--pass-plugin", plugin, "--pass-plugin", plugin,
                   "--pass-pipeline", "builtin.module(naru-test-mark)", "-o", work / "repeated-pass.mlir")
            plugin = ROOT / "target/naru_device_plugin.dll"
            invoke("build", ROOT / "examples/native_device.nru", "--rules", ROOT / "dialects/native_device.stx",
                   "--dialect-plugin", plugin, "--dialect-plugin", plugin, "-o", work / "repeated-dialect.mlir")
        check("duplicate IRDL and plugin inputs including hardlinks load once", repeated_extensions)

        def conflicting_irdl():
            irdl = ROOT / "backend/examples/device.irdl.mlir"
            other = work / "conflicting-device.mlir"
            other.write_bytes(irdl.read_bytes())
            out = work / "conflicting-device-output.mlir"
            out.write_text("previous-success")
            diagnostic = invoke("build", ROOT / "examples/device.nru", "--rules", ROOT / "dialects/custom_device.stx",
                   "--irdl", irdl, "--irdl", other, "-o", out, expected=1)
            assert "IRDL dialect is already registered: naru_device" in diagnostic, diagnostic
            assert out.read_text() == "previous-success"
        check("conflicting IRDL namespaces report an error without crashing", conflicting_irdl)

        def bad_plugin():
            out = work / "protected.mlir"
            out.write_text("previous-success")
            diagnostic = invoke("build", source, "--rules", base, "--pass-plugin", work / "missing.dll", "-o", out, expected=1)
            assert "missing.dll" in diagnostic and out.read_text() == "previous-success", diagnostic
        check("plugin failure preserves the artifact", bad_plugin)

        def failure_report():
            out, report = work / "bad-pass.mlir", work / "bad-pass.json"
            invoke("build", source, "--rules", base, "--pass-pipeline", "builtin.module(does-not-exist)",
                   "-o", out, "--report", report, expected=1)
            info = json.loads(report.read_text())
            assert info["success"] is False and info["processes_spawned"] == 0 and info["error"], info
            assert not out.exists()
        check("failed pass emits a native backend report", failure_report)

        def integer_bounds():
            program, rules = work / "unit.nru", work / "integer.stx"
            program.write_text("unit\n")
            for value, valid in (("255", True), ("256", False), ("-128", True), ("-129", False)):
                rules.write_text('mod integer; syntax item `unit` => Unit();\n'
                    'effect emit(Unit()) => mlir.op("arith.constant", [], ["i8"], '
                    '[Attr("value", ' + value + ', "i8")], []);\n')
                out = work / ("integer-" + value + ".mlir")
                invoke("emit", program, "--rules", rules, "-o", out, expected=0 if valid else 1)
                assert out.exists() == valid
        check("integer attributes reject truncation and signed overflow", integer_bounds)

        def unknown_operation():
            program, rules = work / "unknown.nru", work / "unknown.stx"
            program.write_text("unit\n")
            rules.write_text('mod unknown; syntax item `unit` => Unit();\n'
                            'effect emit(Unit()) => mlir.op("arith.missing_operation", [], [], [], []);\n')
            diagnostic = invoke("emit", program, "--rules", rules, expected=1)
            assert "arith.missing_operation" in diagnostic, diagnostic
        check("unknown operation in a registered dialect is rejected", unknown_operation)

        def bad_branch():
            rules = work / "branch.stx"
            rules.write_text((ROOT / "dialects/control_flow.stx").read_text().replace("[constant(0), constant(0)]", "[constant(0)]"))
            diagnostic = invoke("build", ROOT / "tests/fixtures/raw_cfg.nru", "--rules", rules, "-o", work / "bad-branch.mlir", expected=1)
            assert "branch" in diagnostic and "operand" in diagnostic and "target block has 2" in diagnostic, diagnostic
        check("MLIR verifies branch operand counts", bad_branch)

        if args.frozen:
            def frozen():
                out = work / "frozen.exe"
                invoke("build", source, "--target", "exe", "-o", out, cwd=work, compiler=args.frozen.resolve())
                assert execute([str(out)], cwd=work).returncode == 42
            check("frozen compiler without rules, PATH or child processes", frozen)

        if args.frozen_cfg:
            def frozen_cfg():
                dynamic = invoke("emit", ROOT / "tests/fixtures/raw_cfg.nru", "--rules", ROOT / "dialects/control_flow.stx")
                native = invoke("emit", ROOT / "tests/fixtures/raw_cfg.nru", cwd=work, compiler=args.frozen_cfg.resolve())
                assert dynamic == native, "frozen CFG emission differs from dynamic rules"
                for level in ("0", "3"):
                    out = work / ("frozen-cfg-O" + level + ".exe")
                    invoke("build", ROOT / "tests/fixtures/raw_cfg.nru", "--target", "exe", "--opt-level", level,
                           "--pass-pipeline", "builtin.module()", "-o", out, cwd=work, compiler=args.frozen_cfg.resolve())
                    assert execute([str(out)], cwd=work).returncode == 42
            check("frozen lazy block construction and CFG parity at O0/O3", frozen_cfg)

    report = {"backend": "in-process", "child_processes_prohibited": True,
              "passed": all(item["passed"] for item in results), "tests": results}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{sum(item['passed'] for item in results)}/{len(results)} native compiler checks passed")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
