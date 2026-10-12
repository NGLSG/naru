#!/usr/bin/env python3
"""Boundary tests for parsing, IR regions, and preserving failed outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from run import BASE, Case, ROOT, run_case, source


CASES = [
    Case("declared right associativity nests the right operand",
         source("parse", "tests/fixtures/right_associative.nru", "tests/fixtures/right_associative.stx", BASE),
         tree="right_associative.Power(base.Int(2),right_associative.Power(base.Int(3),base.Int(4)))"),
    Case("parentheses can override right associativity",
         source("parse", "tests/fixtures/right_parenthesized.nru", "tests/fixtures/right_associative.stx", BASE),
         tree="right_associative.Power(right_associative.Power(base.Int(2),base.Int(3)),base.Int(4))"),
    Case("unknown tokens after a complete item are rejected", source("check", "tests/fixtures/trailing_unknown.nru", BASE), False,
         contains=("cannot parse",)),
    Case("unknown expression suffix is rejected", source("check", "tests/fixtures/trailing_expression.nru", BASE), False,
         contains=("cannot parse",)),
    Case("a quoted string cannot match the fn keyword", source("check", "tests/fixtures/quoted_fn.nru", BASE), False,
         contains=("cannot parse",)),
    Case("a quoted string cannot match the return keyword", source("check", "tests/fixtures/quoted_return.nru", BASE), False,
         contains=("cannot parse",)),
    Case("a quoted string cannot declare a core module", source("check", "tests/fixtures/quoted_mod.nru", BASE), False,
         contains=("cannot parse",)),
    Case("a quoted string cannot import a core module", source("check", "tests/fixtures/source_modules/quoted_use.nru", BASE), False,
         contains=("cannot parse",)),
]


def invoke(compiler: Path, arguments: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(compiler), *arguments], cwd=ROOT, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=30)
    assert result.returncode == expected, f"exit={result.returncode}: {result.stdout}{result.stderr}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target" / "naru.exe")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    failures = 0
    for case in CASES:
        failure = run_case(compiler, case, 15.0)
        print(f"{'FAIL' if failure else 'PASS'} {case.name}")
        if failure:
            print(failure)
            failures += 1
    passed = len(CASES) - failures
    try:
        with tempfile.TemporaryDirectory(prefix="naru boundaries ") as directory:
            work = Path(directory)
            raw = work / "regions.mlir"
            invoke(compiler, ["emit", "tests/fixtures/region_isolation.nru", "--rules", BASE,
                              "--rules", "tests/fixtures/region_isolation.stx", "-o", str(raw)])
            text = raw.read_text(encoding="utf-8")
            assert "999" not in text and text.count('"arith.constant"') == 2, text
            optimized = work / "regions.optimized.mlir"
            invoke(compiler, ["build", "tests/fixtures/region_isolation.nru", "--rules", BASE,
                              "--rules", "tests/fixtures/region_isolation.stx", "-o", str(optimized)])
            text = optimized.read_text(encoding="utf-8")
            assert len(re.findall(r"func\.func\s+@(?:first|second)", text)) == 2, text
            print("PASS lazy unselected IR branch emits nothing and sibling regions stay isolated")
            passed += 1

            sentinel = b"last successful artifact\r\n"
            for label, arguments in (
                ("parse failure", ["emit", "tests/fixtures/malformed.nru", "--rules", BASE]),
                ("effect failure", ["emit", "tests/fixtures/unknown_effect.nru", "--rules", "tests/fixtures/unknown_effect.stx"]),
                ("MLIR verification failure", ["build", "tests/fixtures/invalid_ir.nru", "--rules", BASE,
                                               "--rules", "tests/fixtures/invalid_ir.stx"]),
                ("unknown pass failure", ["build", "examples/answer.nru", "--rules", BASE,
                                          "--pass-pipeline", "builtin.module(naru-no-such-pass)"]),
            ):
                artifact = work / "existing.mlir"
                artifact.write_bytes(sentinel)
                result = invoke(compiler, [*arguments, "-o", str(artifact)], expected=1)
                assert result.stdout.strip() or result.stderr.strip(), "failure lacked a diagnostic"
                assert artifact.read_bytes() == sentinel, f"{label} overwrote the last successful artifact"
                print(f"PASS {label} preserves the existing output")
                passed += 1

            main_source = work / "main.nru"
            dependency = work / "dependency.nru"
            main_source.write_text("mod main;\nuse dependency;\nfn main() -> i32 { return 42; }\n", encoding="utf-8")
            dependency.write_text("mod dependency;\nfn dep() -> i32 { return 1; }\n", encoding="utf-8")
            invoke(compiler, ["check", str(main_source), "--rules", BASE])
            print("PASS source imports resolve in long external paths containing spaces")
            passed += 1

            before = dependency.read_bytes()
            result = invoke(compiler, ["emit", str(main_source), "--rules", BASE, "-o", str(dependency)], expected=2)
            assert "overwrite" in result.stdout + result.stderr
            assert dependency.read_bytes() == before, "output overwrote an imported program dependency"
            print("PASS output cannot overwrite a transitive source dependency")
            passed += 1

            nul_source = work / "nul.nru"
            nul_source.write_bytes(b"fn main() -> i32 { return 42; }\n\x00unrecognized trailing data\n")
            result = invoke(compiler, ["check", str(nul_source), "--rules", BASE], expected=1)
            assert "NUL" in result.stdout + result.stderr
            nul_rules = work / "nul.stx"
            nul_rules.write_bytes(b"mod nul;\nsyntax item `ok` => Ok();\n\x00unrecognized trailing data\n")
            result = invoke(compiler, ["check", str(main_source), "--rules", str(nul_rules)], expected=1)
            assert "NUL" in result.stdout + result.stderr
            print("PASS embedded NUL bytes cannot hide invalid source or rule suffixes")
            passed += 1

            hardlink = work / "source_alias.mlir"
            hardlink.hardlink_to(main_source)
            main_before = main_source.read_bytes()
            result = invoke(compiler, ["emit", str(main_source), "--rules", BASE, "-o", str(hardlink)], expected=2)
            assert "overwrite" in result.stdout + result.stderr
            assert main_source.read_bytes() == main_before and hardlink.read_bytes() == main_before, \
                "writing through a hardlink alias changed a source input"
            print("PASS output cannot overwrite source through a hardlink alias")
            passed += 1

            artifact = work / "profile_collision.mlir"
            profile = work / "profile_collision.mlir.input.mlir"
            profile.write_text(json.dumps({"name": "collision-test", "pipeline": "builtin.module(canonicalize,cse)"}), encoding="utf-8")
            profile_before = profile.read_bytes()
            invoke(compiler, ["build", "examples/answer.nru", "--rules", BASE,
                              "--target", str(profile), "-o", str(artifact)])
            assert profile.read_bytes() == profile_before, "temporary IR overwrote the target profile"
            assert artifact.is_file() and "arith.constant 42" in artifact.read_text(encoding="utf-8")
            print("PASS target profile may occupy the former fixed temporary-IR pathname")
            passed += 1

            literal_rules = work / "token_kinds.stx"
            literal_rules.write_text('mod token_kinds;\nsyntax item `"fn"` => Quoted();\nsyntax item `fn` => Bare();\n', encoding="utf-8")
            literal_source = work / "token_kinds.nru"
            for spelling, constructor in (('"fn"', "Quoted"), ("fn", "Bare")):
                literal_source.write_text(spelling + "\n", encoding="utf-8")
                result = invoke(compiler, ["parse", str(literal_source), "--rules", str(literal_rules)])
                assert result.stdout.strip() == f"[token_kinds.{constructor}()]", result.stdout + result.stderr
            print("PASS fixed quoted literals and same-text keywords remain distinct grammar rules")
            passed += 1
    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
        print(f"FAIL {error}", file=sys.stderr)
        failures += 1
    print(f"\n{passed} boundary checks passed, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
