#!/usr/bin/env python3
"""Black-box language-contract tests for the Vyx-built Naru executable."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    name: str
    arguments: tuple[str, ...]
    succeeds: bool = True
    contains: tuple[str, ...] = ()
    tree: str | None = None


def source(command: str, path: str, *rules: str, relation: str | None = None) -> tuple[str, ...]:
    arguments = [command, path]
    for rule in rules:
        arguments.extend(("--rules", rule))
    if relation:
        arguments.extend(("--relation", relation))
    return tuple(arguments)


def evaluate(expression: str, *rules: str) -> tuple[str, ...]:
    arguments = ["eval", "--expr", expression]
    for rule in rules:
        arguments.extend(("--rules", rule))
    return tuple(arguments)


def qualified(module: str, tree: str) -> str:
    """Expected constructors retain their defining module's semantic identity."""
    return re.sub(r"(?<![\w.])([A-Z]\w*)(?=\()", lambda match: module + "." + match[1], tree)


BASE = "dialects/base.stx"
ALT = "dialects/alternate.stx"
OWN = "dialects/ownership.stx"
UNLESS = "dialects/unless.stx"
LOOPS = "dialects/loops.stx"
STANDARD = "dialects/standard.stx"


CASES = [
    Case("default project manifest selects dialect and source entry", ("parse",),
         tree=qualified("base", 'Function("main",Add(Int(2),Mul(Int(8),Int(5))))')),
    Case("explicit rules bypass the default project relation", source("check", "examples/ownership/valid.nru", OWN)),
    Case("ordinary source needs no stx import", source("check", "examples/answer.nru", BASE)),
    Case("core module declaration precedes dialect items", source("parse", "tests/fixtures/module.nru", BASE),
         tree=qualified("base", 'Function("main",Int(42))')),
    Case("duplicate program module declaration is rejected", source("check", "tests/fixtures/duplicate_module.nru", BASE), False),
    Case("alternate spelling reuses function semantics", source("parse", "examples/alternate.nru", BASE, ALT),
         tree=qualified("base", "Add(Int(2),Mul(Int(8),Int(5)))")),
    Case("rule imports resolve independently of loading order", source("parse", "examples/alternate.nru", ALT, BASE),
         tree=qualified("base", "Add(Int(2),Mul(Int(8),Int(5)))")),
    Case("rule package imports automatically load dependencies", source("parse", "examples/alternate.nru", ALT),
         tree=qualified("base", "Add(Int(2),Mul(Int(8),Int(5)))")),
    Case("standard dialect composes base ownership resources and loops", source("parse", "examples/typed_calls.nru", STANDARD)),
    Case("standard facade analyzes mixed ownership and base items",
         source("check", "tests/fixtures/composed.nru", STANDARD, relation="standard.analyze") + ("--unit", "program"),
         contains=("ownership.Moved()", "base.CheckedFunction")),
    Case("standard facade keeps base whole-program forward calls",
         source("check", "examples/typed_calls.nru", STANDARD, relation="standard.analyze") + ("--unit", "program"),
         contains=("base.Invoke(\"forty\"", "check passed")),
    Case("standard facade lowers mixed items through base MLIR rules",
         source("emit", "tests/fixtures/composed.nru", STANDARD, relation="standard.emit_program") + ("--unit", "program"),
         contains=("\"func.func\"", "\"arith.constant\"", "value = 42 : i32")),
    Case("dotted rule imports prefer hierarchical module paths",
         evaluate("test()", "tests/fixtures/modules/nested_rules/root.stx"),
         tree="pkg.inner.Nested()"),
    Case("canonical rule paths prevent duplicate loading", source("check", "examples/answer.nru", BASE, "./dialects/base.stx")),
    Case("qualified rule references still require imports", evaluate("without_import.test()", "tests/fixtures/modules/without_import.stx", "tests/fixtures/modules/a.stx"), False,
         contains=("not visible",)),
    Case("ambiguous imported relation requires qualification", evaluate("ambiguous_import.test()", "tests/fixtures/modules/ambiguous_import.stx"), False,
         contains=("ambiguous rule symbol",)),
    Case("rules may explicitly extend an imported relation", evaluate("extension.test()", "tests/fixtures/modules/extension.stx"),
         tree="extension.Extended()"),
    Case("guards may inspect pure paths and loaded module metadata", evaluate("path_guard.check()", "tests/fixtures/path_guard.stx"),
         tree="42"),
    Case("different files cannot define the same module", evaluate("a.run(a.X())", "tests/fixtures/modules/a.stx", "tests/fixtures/modules/a_duplicate.stx"), False,
         contains=("duplicate rule module",)),
    Case("multiplication binds tighter than addition", source("parse", "tests/fixtures/precedence.nru", BASE),
         tree=qualified("base", "Add(Int(2),Mul(Int(3),Int(4)))")),
    Case("subtraction associates to the left", source("parse", "tests/fixtures/associativity.nru", BASE),
         tree=qualified("base", "Sub(Sub(Int(8),Int(3)),Int(1))")),
    Case("parentheses override binding power", source("parse", "tests/fixtures/parentheses.nru", BASE),
         tree=qualified("base", "Mul(Add(Int(2),Int(3)),Int(4))")),
    Case("generic MLIR operations and region", source("emit", "examples/answer.nru", BASE),
         contains=('"func.func"', '"arith.constant"', '"arith.addi"', '"arith.muli"', '"func.return"')),
    Case("alternate spelling shares MLIR lowering", source("emit", "examples/alternate.nru", BASE, ALT),
         contains=('"func.func"', '"arith.addi"', '"func.return"')),
    Case("custom target operation has no LLVM requirement", (*source("emit", "examples/device.nru", "dialects/custom_device.stx"), "--irdl", "backend/examples/device.irdl.mlir"),
         contains=('"naru_device.launch"', "workgroups")),
    Case("unknown keyword has no implicit core meaning", source("check", "tests/fixtures/unknown_syntax.nru", BASE), False),
    Case("malformed program is rejected", source("check", "tests/fixtures/malformed.nru", BASE), False),
    Case("malformed stx is rejected", source("check", "examples/answer.nru", "tests/fixtures/malformed.stx"), False),
    Case("syntax conflicts are diagnosed", source("parse", "examples/answer.nru", BASE, "tests/fixtures/conflict.stx"), False),
    Case("syntax conflicts do not depend on loading order", source("parse", "examples/answer.nru", "tests/fixtures/conflict.stx", BASE), False),
    Case("missing semantic rule is diagnosed", source("emit", "tests/fixtures/unknown_effect.nru", "tests/fixtures/unknown_effect.stx"), False),
    Case("ambiguous effects are diagnosed", evaluate("ambiguous(1)", "tests/fixtures/ambiguous_effect.stx"), False,
         contains=("ambiguous effect",)),
    Case("recursive rules exhaust a budget instead of crashing", evaluate("forever(1)", "tests/fixtures/recursive_effect.stx"), False,
         contains=("budget exhausted",)),
    Case("choose evaluates only its selected branch", evaluate("branch(eq(1,1))", "tests/fixtures/lazy.stx"), tree="lazy_test.Kept()"),
    Case("selected failure propagates", evaluate("branch(eq(1,2))", "tests/fixtures/lazy.stx"), False,
         contains=("unchosen branch evaluated",)),
    Case("exact rule arithmetic accepts the minimum i32 value", evaluate("add(-2147483648,0)", BASE),
         tree="-2147483648"),
    Case("rule arithmetic can negate the minimum i32 value", evaluate("mul(-2147483648,-1)", BASE), tree="2147483648"),
    Case("rule arithmetic grows beyond i32", evaluate("add(2147483647,1)", BASE), tree="2147483648"),
    Case("negative rule arithmetic grows beyond i32", evaluate("sub(-2147483648,1)", BASE), tree="-2147483649"),
    Case("single resource move", evaluate("own(Move(),Owned())", OWN), tree="ownership.Moved()"),
    Case("single resource touch", evaluate("own(Touch(),Owned())", OWN), tree="ownership.Owned()"),
    Case("use after move is rejected", evaluate("own(Touch(),Moved())", OWN), False,
         contains=("cannot use a moved resource",)),
    Case("maybe moved use is rejected", evaluate("own(Touch(),MaybeMoved())", OWN), False,
         contains=("cannot use a possibly moved resource",)),
    Case("moving a maybe moved resource is rejected", evaluate("own(Move(),MaybeMoved())", OWN), False,
         contains=("resource may have been moved",)),
    Case("ownership valid sequence", source("check", "examples/ownership/valid.nru", OWN, relation="analyze")),
    Case("ownership branch retains resource", source("check", "examples/ownership/branch_valid.nru", OWN, relation="analyze")),
    Case("ownership branch move rejects later use", source("check", "examples/ownership/branch_invalid.nru", OWN, relation="analyze"), False,
         contains=("cannot use a possibly moved resource",)),
    Case("ownership double move is rejected", source("check", "tests/fixtures/ownership_double_move.nru", OWN, relation="analyze"), False,
         contains=("resource was already moved",)),
    Case("unless extension reuses ownership semantics", source("check", "examples/ownership/unless_valid.nru", OWN, UNLESS, relation="analyze")),
    Case("unless package automatically loads ownership dependency", source("check", "examples/ownership/unless_valid.nru", UNLESS, relation="analyze")),
    Case("unless move rejects later use without analysis changes", source("check", "examples/ownership/unless_invalid.nru", OWN, UNLESS, relation="analyze"), False,
         contains=("cannot use a possibly moved resource",)),
    Case("unless is absent when dialect is unselected", source("check", "examples/ownership/unless_valid.nru", OWN, relation="analyze"), False),
    Case("unless parses into the existing conditional term", source("parse", "examples/ownership/unless_valid.nru", OWN, UNLESS),
         tree=qualified("ownership", "Program(Seq(If(Skip(),Touch()),Move()))")),
    Case("loop extension reaches a fixed point for non-moving bodies", source("check", "examples/ownership/loop_valid.nru", LOOPS, relation="analyze"),
         contains=("ownership.Moved()",)),
    Case("loop extension rejects a move on a later iteration", source("check", "examples/ownership/loop_invalid.nru", LOOPS, relation="analyze"), False,
         contains=("resource may have been moved",)),
    Case("loop extension converges for an already moved untouched resource", evaluate("own(Loop(Skip()),Moved())", LOOPS),
         tree="ownership.Moved()"),
]

# Exhaustive finite-state merge checks: a disagreement must remain conservative.
for left in ("Owned", "Moved", "MaybeMoved"):
    for right in ("Owned", "Moved", "MaybeMoved"):
        expected = left if left == right else "MaybeMoved"
        CASES.append(Case(f"ownership join {left} and {right}",
                          evaluate(f"join({left}(),{right}())", OWN), tree=f"ownership.{expected}()"))


def run_case(compiler: Path, case: Case, timeout: float) -> str | None:
    try:
        result = subprocess.run([str(compiler), *case.arguments], cwd=ROOT, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"timed out after {timeout:g} seconds"
    output = result.stdout + result.stderr
    if (result.returncode == 0) != case.succeeds:
        expectation = "success" if case.succeeds else "a diagnosed failure"
        return f"expected {expectation}, exit={result.returncode}\n{output.strip()}"
    # A signal / access violation is not a satisfactory negative test result.
    if not case.succeeds and (result.returncode < 0 or result.returncode >= 128):
        return f"compiler crashed instead of diagnosing the input, exit={result.returncode}\n{output.strip()}"
    if not case.succeeds and not output.strip():
        return "input was rejected without a diagnostic"
    for fragment in case.contains:
        if fragment not in output:
            return f"missing {fragment!r}\n{output.strip()}"
    if case.tree and case.tree not in re.sub(r"\s+", "", result.stdout):
        return f"missing semantic tree {case.tree!r}\n{output.strip()}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target" / "naru.exe")
    parser.add_argument("--only", default="", help="Run tests whose name contains this text")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--list", action="store_true", help="List tests without running them")
    args = parser.parse_args()
    cases = [case for case in CASES if args.only.lower() in case.name.lower()]
    if not cases:
        parser.error("no tests match --only")
    if args.list:
        for case in cases:
            print(case.name)
        return 0
    compiler = args.compiler.resolve()
    if not compiler.is_file():
        parser.error(f"compiler does not exist: {compiler}; build it before running this suite")
    started = time.perf_counter()
    failures = 0
    for case in cases:
        failure = run_case(compiler, case, args.timeout)
        print(f"{'FAIL' if failure else 'PASS'} {case.name}")
        if failure:
            failures += 1
            print("  " + failure.replace("\n", "\n  "))
    elapsed = time.perf_counter() - started
    print(f"\n{len(cases) - failures}/{len(cases)} passed in {elapsed:.2f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
