"""Exercise ordinary base functions, mutation and CFG lowering end to end."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

PROGRAMS = [
    ("zero iterations", "fn main() -> i32 { var x = 42; while false { x = 0; } return x; }", 42),
    ("parameterized loop and forward call", "fn main() -> i32 { return sum(7); } fn sum(n: i32) -> i32 { var i = 0; var s = 0; while i < n { s = s + i; i = i + 1; } return s + s; }", 42),
    ("branch mutation", "fn main() -> i32 { var x = 0; if true { x = 42; } else { x = 1; } return x; }", 42),
    ("empty branch", "fn main() -> i32 { var x = 42; if false { x = 0; } return x; }", 42),
    ("nested loops and fresh inner initialization", "fn main() -> i32 { var i = 0; var s = 0; while i < 7 { var j = 0; while j < 3 { s = s + 2; j = j + 1; } i = i + 1; } return s; }", 42),
    ("loop declarations do not grow the stack", "fn main() -> i32 { var i = 0; var last = 0; while i < 1000000 { var inner = i; last = inner; i = i + 1; } return last - 999957; }", 42),
    ("branch locals shadow without changing outer bindings", "fn main() -> i32 { var x = 42; if true { var x = 0; x = 1; } return x; }", 42),
    ("early return from nested control flow", "fn f(n: i32) -> i32 { while n > 0 { if n == 1 { return 42; } else { return 2; } } return 0; } fn main() -> i32 { return f(1); }", 42),
    ("immutable bindings inside loop", "fn main() -> i32 { var i = 0; var s = 0; while i < 7 { let value = i * 2; s = s + value; i = i + 1; } return s; }", 42),
    ("signed extension", "fn main() -> i32 { let x: i8 = -1; return (x as i32) + 43; }", 42),
    ("unsigned extension", "fn main() -> i32 { let x: u8 = 255; return (x as i32) - 213; }", 42),
    ("integer truncation", "fn main() -> i32 { let x: u32 = 298; return (x as u8) as i32; }", 42),
    ("modular mutable integer arithmetic", "fn main() -> i32 { var x: u8 = 250; x = x + 48; return x as i32; }", 42),
]
ERRORS = [
    ("immutable assignment", "fn main() -> i32 { let x = 0; x = 1; return x; }", "mutable var"),
    ("parameter assignment", "fn f(x: i32) -> i32 { x = 1; return x; }", "mutable var"),
    ("unknown assignment", "fn main() -> i32 { missing = 1; return 0; }", "unbound environment key"),
    ("assignment type mismatch", "fn main() -> i32 { var x: u32 = 0; x = 1i32; return 0; }", "source type mismatch"),
    ("condition requires bool", "fn main() -> i32 { while 1 { } return 0; }", "source type mismatch"),
    ("loop local cannot escape", "fn main() -> i32 { while false { let inner = 42; } return inner; }", "unbound environment key"),
    ("branch local cannot escape", "fn main() -> i32 { if true { var inner = 42; } return inner; }", "unbound environment key"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true", help="Compiler already contains base rules")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    rules = [] if args.frozen else ["--rules", str(ROOT / "dialects/base.stx")]
    checks, failures = 0, []
    with tempfile.TemporaryDirectory(prefix="naru-base-flow-") as directory:
        work = Path(directory)
        def invoke(*argv):
            return execute([str(compiler), *map(str, argv), *rules, "--unit", "program", "--relation", "base.emit_program"], cwd=ROOT)
        for name, source, expected in PROGRAMS:
            for level in ("0", "2"):
                checks += 1
                label = f"{name} O{level}"
                try:
                    path, exe = work / "program.nru", work / "program.exe"
                    path.write_text(source, encoding="utf-8")
                    built = invoke("build", path, "--target", "exe", "--opt-level", level, "-o", exe)
                    assert built.returncode == 0, built.stdout + built.stderr
                    ran = execute([str(exe)], cwd=work)
                    assert ran.returncode == expected, (ran.returncode, expected)
                    print("PASS " + label)
                except (AssertionError, OSError) as error:
                    failures.append(label)
                    print(f"FAIL {label}: {error}")
        for name, source, diagnostic in ERRORS:
            checks += 1
            path = work / "invalid.nru"
            path.write_text(source, encoding="utf-8")
            result = invoke("emit", path)
            if result.returncode != 1 or diagnostic not in result.stdout + result.stderr:
                failures.append(name)
                print(f"FAIL {name}: {result.stdout}{result.stderr}")
            else:
                print("PASS " + name)
        checks += 1
        path = work / "program.nru"
        path.write_text(PROGRAMS[4][1], encoding="utf-8")
        ir = work / "program.ll"
        result = invoke("build", path, "--target", "llvm-ir", "--opt-level", "2", "-o", ir)
        if result.returncode or any(token in ir.read_text() for token in (" alloca ", " load ", " store ")):
            failures.append("optimized scalar locals have no memory operations")
        else:
            print("PASS optimized scalar locals have no memory operations")
    print(f"{checks-len(failures)}/{checks} ordinary base control-flow checks passed")
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
