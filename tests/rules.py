#!/usr/bin/env python3
"""Public rule contract, open type extensions, and dynamic/AOT parity."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from run import Case, ROOT, evaluate, run_case, source
from native_process import execute

RULES = "tests/fixtures/rule_contract.stx"
BASE = "dialects/base.stx"

CASES = [
    Case("lexical shadowing preserves outer value in initializer", evaluate("rule_contract.scoped(2)", RULES), tree="9"),
    Case("nested bind shadowing", evaluate("bind($x,3,bind($x,add($x,4),mul($x,2)))", RULES), tree="14"),
    Case("repeated binder captures require equality", evaluate("bind([$x,$x],[1,2],$x)", RULES), False, contains=("bind pattern does not match",)),
    Case("conditional rules select negative branch", evaluate("rule_contract.guarded(-12)", RULES), tree="rule_contract.Negative(-12)"),
    Case("conditional rules select nonnegative branch", evaluate("rule_contract.guarded(0)", RULES), tree="rule_contract.Nonnegative(0)"),
    Case("fallback effect permits ordinary extension", evaluate("rule_contract.defaulted(1)", RULES), tree="rule_contract.Specialized()"),
    Case("fallback effect does not depend on declaration order", evaluate("rule_contract.reversed(1)", RULES), tree="rule_contract.Specialized()"),
    Case("fallback effect covers unmatched terms", evaluate("rule_contract.defaulted(42)", RULES), tree="rule_contract.Default(42)"),
    Case("peer fallback rules remain ambiguous", evaluate("rule_contract.ambiguous_default(42)", RULES), False, contains=("ambiguous effect",)),
    Case("integer atoms have canonical equality", evaluate("eq([0001,-000],[1,0])", RULES), tree="1"),
    Case("signed zero is canonical", evaluate("eq(-0,0)", RULES), tree="1"),
    Case("atom kinds are observable without a closed type inventory", evaluate('term.kind("i32")', RULES), tree="1"),
    Case("a false pure guard excludes a matching rule", evaluate('rule_contract.no_effect("hi")', RULES), False, contains=("no matching effect",)),
    Case("overlapping guards remain an error", evaluate("rule_contract.overlap(5)", RULES), False, contains=("ambiguous effect",)),
    Case("guards cannot emit IR", evaluate("rule_contract.unsafe_guard(0)", RULES), False, contains=("guards cannot construct",)),
    Case("guards cannot allocate fresh identities", evaluate("rule_contract.impure_guard(0)", RULES), False, contains=("guards cannot create fresh",)),
    Case("persistent scope shadowing keeps parent untouched", evaluate("rule_contract.immutable()", RULES), tree="[0,7,8]"),
    Case("hygienic symbols are distinct environment keys", evaluate("rule_contract.hygiene()", RULES), tree="[0,1,2]"),
    Case("unbound environment keys diagnose failure", evaluate('env.get(env.empty(),"missing")', RULES), False, contains=("unbound environment key",)),
    Case("polymorphic unknown type and ownership terms unify", evaluate("rule_contract.polymorphic()", RULES),
         tree="rule_contract.Function([rule_contract.Integer(64),rule_contract.Container(rule_contract.Owned(rule_contract.Buffer()))],rule_contract.Integer(64))"),
    Case("library type solver handles open equality constraints", evaluate("types.solve([types.Equal(types.Signed(7),types.Signed(7))],env.empty())", BASE), contains=("types.Solved",)),
    Case("library solver reports structural type mismatch", evaluate("types.solve([types.Equal(types.Signed(7),types.Signed(8))],env.empty())", BASE), tree='types.Rejected("termconstructorsoratomsdonotmatch")'),
    Case("user packages add custom constraint constructors", evaluate("types.solve([constraints.IsOwned(constraints.Owned(constraints.Buffer()))],env.empty())", "dialects/constraints.stx"), contains=("types.Solved",)),
    Case("custom constraint rejects the wrong ownership shape", evaluate("types.solve([constraints.IsOwned(constraints.Shared(constraints.Buffer()))],env.empty())", "dialects/constraints.stx"), tree='types.Rejected("resourceconstraintrequiresOwned(T)")'),
    Case("custom record constraints select an open structural field", evaluate('types.solve([constraints.HasField(constraints.Record([constraints.Field("id",types.Unsigned(64)),constraints.Field("age",types.Signed(16))]),"age",types.Signed(16))],env.empty())', "dialects/constraints.stx"), contains=("types.Solved",)),
    Case("custom record constraints reject an absent field", evaluate('types.solve([constraints.HasField(constraints.Record([constraints.Field("id",types.Unsigned(64))]),"name",types.Signed(32))],env.empty())', "dialects/constraints.stx"), contains=("record field not found: name",)),
    Case("custom record constraints unify a selected field type", evaluate('types.solve([constraints.HasField(constraints.Record([constraints.Field("age",types.Signed(16))]),"age",types.Signed(32))],env.empty())', "dialects/constraints.stx"), contains=("types.Rejected",)),
    Case("occurs check rejects infinite types", evaluate("rule_contract.occurs()", RULES), tree='[0,"occurscheckfailed"]'),
    Case("failed unification rolls back partial bindings", evaluate("rule_contract.rollback()", RULES), tree="[0,0,1]"),
    Case("transitive logic substitutions resolve", evaluate("bind($a,logic.fresh(),bind($b,logic.fresh(),bind([1,$s,$_],logic.unify([$a,$b],[$b,99],env.empty()),logic.resolve([$a,$b],$s))))", RULES), tree="[99,99]"),
    Case("list map invokes an ordinary user relation", evaluate('list.map("rule_contract.square",[2,3,4])', RULES), tree="[4,9,16]"),
    Case("first-class relation application", evaluate('apply("rule_contract.square",[12])', RULES), tree="144"),
    Case("dynamic term constructor remains open", evaluate('term("external.Device",[42])', RULES), tree="external.Device(42)"),
    Case("exact numbers exceed u128", evaluate('add(int.parse("340282366920938463463374607431768211455"),1)', RULES), tree="340282366920938463463374607431768211456"),
    Case("radix and separators normalize exactly", evaluate('int.parse("0xFFFF_FFFF_FFFF_FFFF")', RULES), tree="18446744073709551615"),
    Case("exact signed division truncates toward zero", evaluate("int.div(-100,3)", RULES), tree="-33"),
    Case("exact remainder matches signed division", evaluate("int.rem(-100,3)", RULES), tree="-1"),
    Case("exact large multiplication", evaluate("mul(18446744073709551616,18446744073709551616)", RULES), tree="340282366920938463463374607431768211456"),
    Case("exact negative arithmetic shift", evaluate("int.shr(-9,2)", RULES), tree="-3"),
    Case("minimum signed value fits", evaluate("int.fits(-128,8,1)", RULES), tree="1"),
    Case("positive signed overflow does not fit", evaluate("int.fits(128,8,1)", RULES), tree="0"),
    Case("negative unsigned value does not fit", evaluate("int.fits(-1,128,0)", RULES), tree="0"),
    Case("division by zero diagnoses rather than crashes", evaluate("int.div(1,0)", RULES), False, contains=("division by zero",)),
    Case("malformed integer separator rejected", evaluate('int.parse("1__0")', RULES), False, contains=("separator",)),
    Case("floating conversion exposes IEEE status", evaluate('float.attr("1.25","f64",0)', RULES), tree='["1.250000e+00:f64",0]'),
    Case("APFloat ties round to even and report inexact", evaluate('float.attr("1.00048828125","f16",0)', RULES), tree='["1.000000e+00:f16",16]'),
    Case("APFloat directed rounding changes the selected value", evaluate('float.attr("1.00048828125","f16",2)', RULES), tree='["1.000980e+00:f16",16]'),
    Case("FP8 conversion reports exact APFloat status", evaluate('float.attr("1.5","f8E4M3FN",0)', RULES), tree='["1.500000e+00:f8E4M3FN",0]'),
    Case("scale-only float rounds according to its APFloat format", evaluate('float.attr("1.5","f8E8M0FNU",0)', RULES), tree='["2.000000e+00:f8E8M0FNU",16]'),
    Case("binary operations retain two complement sign extension", evaluate("int.and(-1,42)", RULES), tree="42"),
    Case("multiple resource identities and lexical loans", source("check", "examples/ownership/multiple_resources.nru", "dialects/resources.stx", relation="resources.analyze"), contains=("check passed",)),
    Case("borrowed resource cannot move", source("check", "examples/ownership/borrowed_move.nru", "dialects/resources.stx", relation="resources.analyze"), False, contains=("cannot move a borrowed resource",)),
    Case("sharing permits touch", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.Borrow("a","b"),resources.Touch("a")]))', "dialects/resources.stx"), contains=("resources.State",)),
    Case("exclusive loan prohibits direct touch", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.BorrowMut("a","b"),resources.Touch("a")]))', "dialects/resources.stx"), False, contains=("exclusively borrowed",)),
    Case("exclusive loan conflicts with shared loans", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.Borrow("a","b"),resources.BorrowMut("a","c")]))', "dialects/resources.stx"), False, contains=("exclusive loan conflicts",)),
    Case("shared loan conflicts with exclusive loan", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.BorrowMut("a","b"),resources.Borrow("a","c")]))', "dialects/resources.stx"), False, contains=("shared loan conflicts",)),
    Case("moved resource cannot be borrowed", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.Move("a"),resources.Borrow("a","b")]))', "dialects/resources.stx"), False, contains=("cannot borrow a moved",)),
    Case("loan must be ended once", evaluate('resources.analyze(resources.Program([resources.Own("a",types.Signed(32)),resources.Borrow("a","b"),resources.End("b"),resources.End("b")]))', "dialects/resources.stx"), False, contains=("already ended",)),
    Case("resource branch join rejects a maybe moved value", source("check", "tests/fixtures/resources_branch_maybe.nru", "dialects/resources.stx", relation="resources.analyze"), False, contains=("resource may have been moved",)),
    Case("resource branch join preserves a definite move", source("check", "tests/fixtures/resources_branch_same.nru", "dialects/resources.stx", relation="resources.analyze"), contains=("check passed",)),
    Case("branch-local loan can close before the join", source("check", "tests/fixtures/resources_branch_closed_loan.nru", "dialects/resources.stx", relation="resources.analyze"), contains=("check passed",)),
    Case("active loan cannot escape a resource branch", source("check", "tests/fixtures/resources_branch_active_loan.nru", "dialects/resources.stx", relation="resources.analyze"), False, contains=("loan remains active after branch",)),
    Case("nested resource branches compose through the same join", source("check", "tests/fixtures/resources_nested_branch.nru", "dialects/resources.stx", relation="resources.analyze"), contains=("check passed",)),
    Case("rules can access the source module graph", source("check", "tests/fixtures/source_modules/diamond.nru", BASE, "tests/fixtures/source_inspect.stx", relation="source_inspect.inspect") + ("--unit", "program"), tree='[["common",0,1],["left",1,1],["right",1,1],["diamond",2,1]]'),
]

def invoke(compiler: Path, arguments: list[str], expected: int = 0) -> subprocess.CompletedProcess[str]:
    result = execute([str(compiler), *arguments], cwd=ROOT)
    assert result.returncode == expected, f"exit {result.returncode}\n{result.stdout}{result.stderr}"
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--frozen-rules", type=Path)
    parser.add_argument("--frozen-resources", type=Path)
    parser.add_argument("--frozen-money", type=Path)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    failures: list[str] = []
    checks = 0
    def check(name, task):
        nonlocal checks
        checks += 1
        try:
            task()
            print("PASS " + name)
        except (AssertionError, OSError, subprocess.TimeoutExpired) as exc:
            failures.append(name)
            print(f"FAIL {name}\n{exc}")
    for case in CASES:
        def task(case=case):
            diagnostic = run_case(compiler, case, 20)
            assert diagnostic is None, diagnostic
            selected_frozen = args.frozen_rules if RULES in case.arguments else args.frozen_resources if "dialects/resources.stx" in case.arguments else None
            if selected_frozen:
                common: list[str] = []
                skip_rule_path = False
                for argument in case.arguments:
                    if skip_rule_path:
                        skip_rule_path = False
                    elif argument == "--rules":
                        skip_rule_path = True
                    else:
                        common.append(argument)
                dynamic = invoke(compiler, list(case.arguments), 0 if case.succeeds else 1)
                frozen = invoke(selected_frozen.resolve(), common, 0 if case.succeeds else 1)
                assert (dynamic.stdout, dynamic.stderr) == (frozen.stdout, frozen.stderr), "dynamic/AOT rule mismatch"
        check(case.name, task)
    with tempfile.TemporaryDirectory(prefix="naru type contract ") as directory:
        work = Path(directory)
        def program(name: str, code: str, tokens=(), error: str | None = None, rules: str = BASE):
            path = work / (name + ".nru")
            path.write_text(code, encoding="utf-8")
            common = ["emit", str(path), "--unit", "program", "--relation", "emit_program"]
            dynamic = invoke(compiler, [*common, "--rules", str(ROOT / rules)], 1 if error else 0)
            output = dynamic.stdout + dynamic.stderr
            for token in tokens:
                assert token in output, f"missing {token!r}:\n{output}"
            if error:
                assert error in output, output
            if args.frozen and rules == BASE:
                frozen = invoke(args.frozen.resolve(), common, 1 if error else 0)
                assert (dynamic.stdout, dynamic.stderr) == (frozen.stdout, frozen.stderr), f"dynamic/AOT source mismatch:\n{dynamic.stdout}\n{frozen.stdout}"
            if args.frozen_money and rules == "dialects/money.stx":
                frozen = invoke(args.frozen_money.resolve(), common, 1 if error else 0)
                assert (dynamic.stdout, dynamic.stderr) == (frozen.stdout, frozen.stderr), f"dynamic/AOT custom type mismatch:\n{dynamic.stdout}\n{frozen.stdout}"
        for signed in (True, False):
            for width in (8, 16, 32, 64, 128, 257):
                typename = ("i" if signed else "u") + (str(width) if width != 257 else "<257>")
                high = (1 << (width - 1 if signed else width)) - 1
                low = -(1 << (width - 1)) if signed else 0
                for boundary, value in (("minimum", low), ("maximum", high)):
                    check(f"{typename} {boundary} exact literal", lambda typename=typename, value=value, width=width:
                        program("bounds", f"fn f() -> {typename} {{ return {value}; }}", (f"-> i{width}",)))
                check(f"{typename} overflow belongs to rules", lambda typename=typename, high=high:
                    program("overflow", f"fn f() -> {typename} {{ return {high + 1}; }}", error="outside declared type range"))
        real_types = (
            "f16", "bf16", "f32", "f64", "f80", "f128", "tf32",
            "f8E5M2", "f8E5M2FNUZ", "f8E5M3FNU", "f8E4M3", "f8E4M3FN",
            "f8E4M3FNUZ", "f8E4M3B11FNUZ", "f8E3M4", "f8E8M0FNU",
            "f6E2M3FN", "f6E3M2FN", "f4E2M1FN",
        )
        for typename in real_types:
            check(f"{typename} typed literal and MLIR verification", lambda typename=typename:
                program("floating", f"fn f() -> {typename} {{ return 1.5{typename}; }}", (f"-> {typename}",)))
        for typename in ("f16", "bf16", "f32", "f64", "f80", "f128", "tf32",
                         "f8E5M2", "f8E4M3FN", "f8E4M3FNUZ", "f6E2M3FN", "f4E2M1FN"):
            check(f"{typename} contextual real arithmetic", lambda typename=typename:
                program("floating_arithmetic", f"fn f(a: {typename}) -> {typename} {{ return a + 1.25; }}", ('"arith.addf"', f"-> {typename}")))
        for name, code, error in (
            ("signed unsigned mixing", "fn f(a: u8, b: i8) -> u8 { return a + b; }", "source type mismatch"),
            ("wrong return type", "fn f() -> bool { return 1; }", "no matching effect"),
            ("wrong literal suffix", "fn f() -> i32 { return 42u32; }", "source type mismatch"),
            ("unsigned negative", "fn f() -> u8 { return -1; }", "outside declared type range"),
            ("unknown local", "fn f() -> i32 { return missing; }", "unbound environment key"),
            ("duplicate parameters", "fn f(a: i32, a: i32) -> i32 { return a; }", "duplicate parameter"),
            ("wrong call arity", "fn f(a: i32) -> i32 { return a; } fn main() -> i32 { return f(); }", "argument count"),
            ("duplicate functions", "fn f() -> i32 { return 1; } fn f() -> i32 { return 2; }", "duplicate function"),
            ("float overflow policy", "fn f() -> f32 { return 1.0e100; }", "floating literal overflow"),
            ("float underflow policy", "fn f() -> f32 { return 1.0e-100; }", "floating literal overflow"),
        ):
            check(name, lambda name=name, code=code, error=error: program(name, code, error=error))
        check("unary precedence is independent of multiplication", lambda:
            program("unary", "fn f(a: i32) -> i32 { return -a + 2; }", ('"arith.subi"', '"arith.addi"')))
        check("source boolean wins over identifier fallback", lambda:
            program("boolean", "fn f() -> bool { return true; }", ("value = true", "-> i1")))
        check("negative hexadecimal literal is an integer", lambda:
            program("radix", "fn f() -> i64 { return -0xFE; }", ("-254 : i64",)))
        check("hexadecimal floating literal reaches APFloat", lambda:
            program("hex_float", "fn f() -> f32 { return 0x1.fp3; }", ("1.550000e+01 : f32",)))
        check("minimum suffixed signed literal parses as one value", lambda:
            program("min_suffix", "fn f() -> i8 { return -128i8; }", ("-128 : i8",)))
        check("integer bitwise operations are typed", lambda:
            program("bitwise", "fn f(a: u64, b: u64) -> u64 { return a & b | (a ^ b); }", ('"arith.andi"', '"arith.ori"', '"arith.xori"')))
        check("comparison predicates retain signedness", lambda:
            program("comparison", "fn s(a: i32, b: i32) -> bool { return a > b; } fn u(a: u32, b: u32) -> bool { return a > b; }", ('predicate = 4', 'predicate = 8')))
        check("unknown user type extends existing library", lambda:
            program("money", "fn f(a: cents) -> cents { let fee: cents = 12; return a + fee; }", ('"arith.addi"', "(i64) -> i64"), rules="dialects/money.stx"))
        check("all composite types pass MLIR verifier", lambda:
            invoke(compiler, ["emit", str(ROOT / "examples/numeric_types.nru"), "--rules", str(ROOT / BASE), "--unit", "program", "--relation", "emit_program"]))
        check("rank-2 vector and tensor shapes lower to MLIR", lambda:
            program("rank2_shapes",
                    "fn v(a: vector<2 x 3, f32>) -> vector<2 x 3, f32> { return a; } "
                    "fn t(a: tensor<2 x 3, f32>) -> tensor<2 x 3, f32> { return a; }",
                    ("vector<2x3xf32>", "tensor<2x3xf32>")))
        check("shaped dialect lowers vector and tensor extraction", lambda:
            program("shape_extract",
                    "fn v(a: vector<2 x 3, f32>) -> f32 { return a[1][2]; } "
                    "fn t(a: tensor<4, f32>) -> f32 { return a[2]; }",
                    ('"vector.extract"', '"tensor.extract"', "static_position = array<i64: 1>"),
                    rules="dialects/shapes.stx"))
        check("shaped dialect diagnoses static index bounds", lambda:
            program("shape_bounds", "fn v(a: vector<4, f32>) -> f32 { return a[4]; }",
                    error="outside the first dimension", rules="dialects/shapes.stx"))
        check("target sized index type lowers through ordinary rules", lambda:
            program("index", "fn add(a: index) -> index { return a + 1; } fn less(a: index, b: index) -> bool { return a < b; }",
                    ("function_type = (index) -> index", '"arith.addi"', '"arith.cmpi"')))
        def native():
            for level in ("0", "3"):
                executable = work / ("answer" + level + ".exe")
                common = ["build", str(ROOT / "examples/typed_calls.nru"), "--unit", "program", "--relation", "emit_program", "--target", "exe", "--opt-level", level, "-o", str(executable)]
                invoke(compiler, [*common, "--rules", str(ROOT / BASE)])
                invoke(executable, [], 42)
                if args.frozen:
                    invoke(args.frozen.resolve(), common)
                    invoke(executable, [], 42)
        check("forward calls and hygienic shadowing run at O0 and O3 without child processes", native)
    record = {"passed": checks - len(failures), "total": checks, "failures": failures,
              "dynamic_aot_types": bool(args.frozen), "dynamic_aot_rules": bool(args.frozen_rules),
              "dynamic_aot_resources": bool(args.frozen_resources), "dynamic_aot_custom_types": bool(args.frozen_money)}
    (ROOT / "tests/rules-verification.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"\n{record['passed']}/{checks} rule and type contracts passed")
    return bool(failures)

if __name__ == "__main__":
    raise SystemExit(main())
