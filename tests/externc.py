"""Check rule-library C declarations, static strings and real Windows x64 C calls."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

PROGRAMS = [
    ("empty extern block", 'extern "C" {} fn main() -> i32 { return 42; }'),
    ("unused external declaration has no entry block", 'extern "C" { fn add(a: i32, b: i32) -> i32; } fn main() -> i32 { return 42; }'),
    ("pointer casts and char identity compose with base", 'fn byte(x: char) -> char { return x; } fn pointer() -> *i32 { return (null as ptr) as *i32; } fn main() -> i32 { let x: char = byte(255); let p = pointer(); return 42; }'),
]
ERRORS = [
    ("duplicate external and local symbol", 'extern "C" { fn f() -> i32; } fn f() -> i32 { return 42; }', "duplicate function"),
    ("duplicate external symbol", 'extern "C" { fn f() -> i32; fn f() -> i32; }', "duplicate function"),
    ("foreign argument count", 'extern "C" { fn f(a: i32) -> i32; } fn main() -> i32 { return f(); }', "function argument count mismatch"),
    ("foreign argument type", 'extern "C" { fn f(a: i32) -> i32; } fn main() -> i32 { return f(1u32); }', "source type mismatch"),
    ("unsupported ABI type", 'extern "C" { fn f(a: i128) -> i32; }', "unsupported extern C ABI type"),
    ("unsupported ABI pointee", 'extern "C" { fn f(a: *i128) -> i32; }', "unsupported extern C ABI type"),
    ("char upper bound", 'fn f() -> char { return 256; }', "integer literal outside declared type range"),
    ("char lower bound", 'fn f() -> char { return -1; }', "integer literal outside declared type range"),
    ("string pointee mismatch", 'fn f() -> *i32 { return "bad"; }', "C string literal expects *char or ptr"),
    ("null requires pointer", 'fn f() -> i32 { return null; }', "null requires a pointer type"),
    ("embedded NUL escape", r'fn f() -> ptr { return "a\0b"; }', "invalid string escape"),
]

# The Naru function precedes its declarations to exercise forward lookup.
# C independently checks widths, argument registers, UTF-8 bytes and NUL storage.
FFI_SOURCE = r'''
fn answer() -> i32 {
    let value = c_add(20, 22);
    let text: *char = "Naru中文\n\"\\";
    return value + c_string(text) + c_null(null) + c_char(255)
        + c_i8(-1) + c_i16(-123) + c_i64(-1234567890123)
        + c_u8(255) + c_u16(65535) + c_u32(4294967295)
        + c_u64(18446744073709551615) + c_f32(1.5) + c_f64(2.5)
        + c_zero() + c_string_return(return_text() as ptr);
}
fn return_text() -> *char { return "Naru中文\n\"\\"; }
extern "C" {
    fn c_add(a: i32, b: i32) -> i32;
    fn c_string(p: *char) -> i32;
    fn c_string_return(p: ptr) -> i32;
    fn c_null(p: *i32) -> i32;
    fn c_char(x: char) -> i32;
    fn c_i8(x: i8) -> i32;
    fn c_i16(x: i16) -> i32;
    fn c_i64(x: i64) -> i32;
    fn c_u8(x: u8) -> i32;
    fn c_u16(x: u16) -> i32;
    fn c_u32(x: u32) -> i32;
    fn c_u64(x: u64) -> i32;
    fn c_f32(x: f32) -> i32;
    fn c_f64(x: f64) -> i32;
    fn c_zero() -> i32;
}
'''
FFI_HARNESS = r'''
#include <stdint.h>
#include <string.h>
int32_t c_add(int32_t a, int32_t b) { return a + b; }
int32_t c_string(const unsigned char *p) {
    const unsigned char expected[] = {78,97,114,117,228,184,173,230,150,135,10,34,92,0};
    return memcmp(p, expected, sizeof(expected)) != 0;
}
int32_t c_string_return(const void *p) { return c_string(p); }
int32_t c_null(const int32_t *p) { return p != 0; }
int32_t c_char(unsigned char x) { return x != 255; }
int32_t c_i8(int8_t x) { return x != -1; }
int32_t c_i16(int16_t x) { return x != -123; }
int32_t c_i64(int64_t x) { return x != INT64_C(-1234567890123); }
int32_t c_u8(uint8_t x) { return x != 255; }
int32_t c_u16(uint16_t x) { return x != 65535; }
int32_t c_u32(uint32_t x) { return x != UINT32_C(4294967295); }
int32_t c_u64(uint64_t x) { return x != UINT64_C(18446744073709551615); }
int32_t c_f32(float x) { return x != 1.5f; }
int32_t c_f64(double x) { return x != 2.5; }
int32_t c_zero(void) { return 0; }
extern int32_t answer(void);
int main(void) { return answer(); }
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--cc", default=shutil.which("clang"), help="Host Clang used only to link the independent C harness")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    rules = [] if args.frozen else ["--rules", str(ROOT / "dialects/externc.stx")]
    checks, failures = 0, []
    with tempfile.TemporaryDirectory(prefix="naru-extern-c-") as directory:
        work = Path(directory)
        source, output = work / "program.nru", work / "program.exe"

        def invoke(command, *argv):
            return execute([str(compiler), command, str(source), *map(str, argv), *rules,
                            "--unit", "program", "--relation", "emit_program"],
                           cwd=work, env=dict(os.environ, PATH=""))

        def check(label, body):
            nonlocal checks
            checks += 1
            try:
                body()
                print("PASS " + label)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                failures.append(label)
                print(f"FAIL {label}: {error}")

        def success(result):
            assert result.returncode == 0, result.stdout + result.stderr
            return result.stdout

        def native(program, level):
            source.write_text(program, encoding="utf-8")
            success(invoke("build", "--target", "exe", "--opt-level", level, "-o", output))
            ran = execute([str(output)], cwd=work)
            assert ran.returncode == 42, ran.returncode

        for level in ("0", "2"):
            check(f"user sum_loop command O{level}", lambda: native((ROOT / "examples/sum_loop.nru").read_text(), level))
            for label, program in PROGRAMS:
                check(f"{label} O{level}", lambda: native(program, level))

        for label, program, diagnostic in ERRORS:
            def reject():
                source.write_text(program, encoding="utf-8")
                result = invoke("emit")
                assert result.returncode == 1 and diagnostic in result.stdout + result.stderr, result.stdout + result.stderr
            check(label, reject)

        def strings(literal, byte_count):
            source.write_text(f'fn first() -> *char {{ return "{literal}"; }} fn second() -> ptr {{ return "{literal}"; }}', encoding="utf-8")
            ir = success(invoke("emit"))
            assert ir.count('"llvm.mlir.global"') == 1, ir
            assert ir.count('"llvm.mlir.addressof"') == 2, ir
            assert f"!llvm.array<{byte_count} x i8>" in ir, ir
            llvm = work / "strings.ll"
            success(invoke("build", "--target", "llvm-ir", "--opt-level", "0", "-o", llvm))
            assert "constant" in llvm.read_text(), llvm.read_text()

        check("empty strings share static NUL storage", lambda: strings("", 1))
        check("UTF-8 and escaped strings share static storage", lambda: strings(r'Naru中文\n\"\\', 14))
        check("long string does not exhaust rule depth", lambda: strings("a" * 1024, 1025))

        def c_calls(level):
            assert args.cc, "Host Clang is required for the independent C ABI harness (use --cc)"
            source.write_text(FFI_SOURCE, encoding="utf-8")
            obj, harness = work / "program.obj", work / "harness.c"
            harness.write_text(FFI_HARNESS, encoding="utf-8")
            success(invoke("build", "--target", "object", "--opt-level", level, "-o", obj))
            # This is test setup, separate from the guarded Naru compiler process.
            linked = subprocess.run([args.cc, "-O2", "-fuse-ld=lld", str(harness), str(obj), "-o", str(output)],
                                    cwd=work, capture_output=True, text=True, timeout=120)
            success(linked)
            ran = execute([str(output)], cwd=work)
            assert ran.returncode == 42, ran.returncode

        for level in ("0", "2"):
            check(f"C calls validate integer/float/pointer/string ABI O{level}", lambda: c_calls(level))

    print(f"{checks-len(failures)}/{checks} extern C rule checks passed")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
