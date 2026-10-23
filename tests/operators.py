"""User-declared operators and open library candidates, including frozen overlays."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
POINT = "struct P{x:i32;}"
PROGRAMS = [
    ("record, mixed operands, unary and independent result", (ROOT / "examples/operators.nru").read_text(), 42),
    ("source order and forward declaration", POINT + "fn main()->i32{let a=P{x:20};return a+22;}operator +(a:P,b:i32)->i32{return a.x+b;}", 42),
    ("multiple disjoint overloads", POINT + "operator +(a:P,b:P)->i32{return a.x+b.x;}operator +(a:P,b:i32)->i32{return a.x+b;}fn main()->i32{let p=P{x:10};return (p+p)+(p+12);}", 42),
    ("typed literal selects mixed signature", POINT + "operator +(a:P,b:u8)->i32{return a.x+(b as i32);}fn main()->i32{return P{x:20}+22u8;}", 42),
    ("untyped literal uses unique numeric parameter", POINT + "operator +(a:P,b:u8)->i32{return a.x+(b as i32);}fn main()->i32{return P{x:20}+22;}", 42),
    ("comparison overload", POINT + "operator ==(a:P,b:P)->bool{return a.x==b.x;}fn main()->i32{if P{x:42}==P{x:42}{return 42;}else{return 0;}}", 42),
    ("bitwise overload", POINT + "operator |(a:P,b:i32)->i32{return a.x|b;}fn main()->i32{return P{x:40}|2;}", 42),
    ("shift overload", POINT + "operator <<(a:P,b:i32)->i32{return a.x<<b;}fn main()->i32{return P{x:21}<<1;}", 42),
    ("negative literal remains numeric beside record unary", POINT + "operator -(a:P)->P{return P{x:-a.x};}fn main()->i32{let p=-P{x:20};return -1-p.x+23;}", 42),
    ("operands evaluated exactly once", POINT + "fn make(n:i32)->P{return P{x:n};}operator +(a:P,b:P)->i32{return a.x+b.x;}fn main()->i32{return make(20)+make(22);}", 42),
]
AFFINE = [
    ("owned consuming overload", "operator +(a:owned<i32>,b:i32)->i32{let r=&a;return *r+b;}fn main()->i32{let a=own(20);return move a+22;}", 42),
    ("borrowed overload", "operator +(a:ref<i32>,b:i32)->i32{return *a+b;}fn main()->i32{let a=own(20);let r=&a;let n=r+22;end r;return n;}", 42),
    ("operator body participates in closure and defer phases", POINT + "fn consume(n:i32)->void{}operator +(a:P,b:i32)->i32{defer consume(b);let f=fn[b](n:i32)->i32{return b+n;};return f(a.x);}fn main()->i32{return P{x:20}+22;}", 42),
]
ERRORS = [
    ("duplicate parameter signature", POINT + "operator +(a:P,b:i32)->i32{return 1;}operator +(a:P,b:i32)->i32{return 2;}fn main()->i32{return 0;}", "duplicate operator overload"),
    ("result alone does not distinguish signatures", POINT + "operator +(a:P,b:i32)->i32{return 1;}operator +(a:P,b:i32)->u32{return 2;}fn main()->i32{return 0;}", "duplicate operator overload"),
    ("ambiguous untyped numeric literal", POINT + "operator +(a:P,b:i32)->i32{return 1;}operator +(a:P,b:u8)->i32{return 2;}fn main()->i32{return P{x:0}+42;}", "ambiguous operator overload"),
    ("overload result still checks caller expectation", POINT + "operator +(a:P,b:P)->bool{return true;}fn main()->i32{return P{x:1}+P{x:2};}", "source type mismatch"),
    ("implicit numeric conversion is not an overload match", POINT + "operator +(a:P,b:u8)->i32{return 42;}fn main()->i32{return P{x:1}+2i32;}", "source type mismatch"),
    ("literal fits selected parameter", POINT + "operator +(a:P,b:u8)->i32{return 42;}fn main()->i32{return P{x:1}+256;}", "outside declared type range"),
    ("operator body checks normally", POINT + "operator +(a:P,b:i32)->i32{return missing;}fn main()->i32{return 0;}", "unbound environment key"),
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true")
    parser.add_argument("--minimal", action="store_true", help="Frozen image contains operators + records rather than standard")
    parser.add_argument("--overlay-standard", action="store_true", help="Load standard as a dynamic extension of the frozen image")
    args = parser.parse_args()
    compiler = args.compiler.resolve(); env = dict(os.environ); env["PATH"] = ""
    rules = [] if args.frozen else ["--rules", str(ROOT / "dialects/standard.stx"), "--rules", str(ROOT / "dialects/types.stx")]
    if args.overlay_standard:
        rules += ["--rules", str(ROOT / "dialects/standard.stx")]
    relation = "base.emit_program" if args.minimal else "standard.emit_program"
    checks = []
    with tempfile.TemporaryDirectory(prefix="naru-operators-") as directory:
        work = Path(directory); source = work / "main.nru"; output = work / "main.exe"
        def invoke(command, *extra):
            return execute([str(compiler), command, str(source), *rules, "--unit", "program", "--relation", relation, *map(str, extra)], cwd=ROOT, env=env, timeout=90)
        def test(name, action):
            try:
                action(); checks.append({"name":name,"passed":True}); print("PASS " + name, flush=True)
            except (AssertionError, OSError) as error:
                checks.append({"name":name,"passed":False,"error":str(error)}); print(f"FAIL {name}: {error}", flush=True)
        for name, program, expected in PROGRAMS + ([] if args.minimal else AFFINE):
            for level in ("0", "2"):
                def native(program=program, expected=expected, level=level):
                    source.write_text(program, encoding="utf-8")
                    result = invoke("build", "--target", "exe", "--opt-level", level, "-o", output)
                    assert result.returncode == 0, result.stdout + result.stderr
                    ran = execute([str(output)], cwd=work, env=env)
                    assert ran.returncode == expected, ran
                test(name + " O" + level, native)
        for name, program, message in ERRORS:
            def reject(program=program, message=message):
                source.write_text(program, encoding="utf-8"); output.write_bytes(b"preserved")
                result = invoke("build", "--target", "exe", "-o", output)
                assert result.returncode == 1 and message in result.stdout + result.stderr, result.stdout + result.stderr
                assert output.read_bytes() == b"preserved"
            test(name, reject)
        extension = ROOT / "tests/fixtures/operators/extension.stx"
        for name, program in [
            ("new operator spelling from dynamic syntax", "fn combine(a:i32,b:i32)->i32{return a+b;}fn main()->i32{return 20@22;}"),
            ("mixed types from dynamic effect", "fn main()->i32{return 20i32+22u8;}"),
            ("existing plus syntax gains a new record meaning", "struct Point{x:i32;}fn translate(a:Point,b:i32)->Point{return Point{x:a.x+b};}fn main()->i32{return (Point{x:20}+22i32).x;}"),
        ]:
            def extend(program=program):
                source.write_text(program, encoding="utf-8")
                built = invoke("build", "--rules", extension, "--target", "exe", "-o", output)
                assert built.returncode == 0, built.stdout + built.stderr
                assert execute([str(output)], cwd=work, env=env).returncode == 42
            test(name, extend)
        def peers():
            source.write_text("fn other(a:i32,b:u8)->i32{return 42;}fn main()->i32{return 20i32+22u8;}", encoding="utf-8")
            result = invoke("check", "--rules", extension, "--rules", ROOT / "tests/fixtures/operators/conflict.stx")
            assert result.returncode == 1 and "ambiguous operator overload" in result.stdout + result.stderr, result.stdout + result.stderr
        test("peer library candidates remain ambiguous", peers)
        def source_peer():
            source.write_text("operator +(a:i32,b:u8)->i32{return 42;}fn main()->i32{return 20i32+22u8;}", encoding="utf-8")
            result = invoke("check", "--rules", extension)
            assert result.returncode == 1 and "ambiguous operator overload" in result.stdout + result.stderr, result.stdout + result.stderr
        test("source and library candidates share one selection", source_peer)
        def syntax_conflict():
            source.write_text("fn main()->i32{return 20+22;}", encoding="utf-8")
            result = invoke("parse", "--rules", ROOT / "tests/fixtures/operators/syntax_conflict.stx")
            assert result.returncode == 1 and "ambiguous" in result.stdout + result.stderr and "syntax" in result.stdout + result.stderr, result.stdout + result.stderr
        test("conflicting AST rewrites are still syntax ambiguity", syntax_conflict)
        def custom_declaration():
            source.write_text("operator @(a:i32,b:i32)->i32{return a+b;}fn main()->i32{return 20@22;}", encoding="utf-8")
            result = invoke("build", "--rules", ROOT / "tests/fixtures/operators/syntax.stx", "--target", "exe", "-o", output)
            assert result.returncode == 0, result.stdout + result.stderr
            assert execute([str(output)], cwd=work, env=env).returncode == 42
        test("a dynamically added spelling accepts source declarations", custom_declaration)
        def missing_custom():
            source.write_text("fn main()->i32{return 20@22;}", encoding="utf-8")
            result = invoke("check", "--rules", ROOT / "tests/fixtures/operators/syntax.stx")
            assert result.returncode == 1 and "no operator overload" in result.stdout + result.stderr, result.stdout + result.stderr
        test("an added spelling still requires a semantic implementation", missing_custom)
        def ir():
            source.write_text(POINT + "operator +(a:P,b:i32)->i32{return a.x+b;}fn main()->i32{return P{x:20}+22;}", encoding="utf-8")
            result = invoke("emit")
            assert result.returncode == 0 and "func.call" in result.stdout and "_naru_operator_" in result.stdout, result.stdout + result.stderr
        test("overload lowers to an ordinary static function call", ir)
        if not args.minimal:
            def evaluated_once():
                source.write_text('extern "C"{fn puts(s:*char)->i32;}struct P{x:i32;}fn make(n:i32)->P{puts("operand");return P{x:n};}operator +(a:P,b:P)->i32{return a.x+b.x;}fn main()->i32{return make(20)+make(22);}', encoding="utf-8")
                result = invoke("build", "--target", "exe", "--runtime", "crt-static", "-o", output)
                assert result.returncode == 0, result.stdout + result.stderr
                ran = execute([str(output)], cwd=work, env=env)
                assert ran.returncode == 42 and ran.stdout.splitlines() == ["operand", "operand"], ran
            test("side effects prove each operand executes once", evaluated_once)
            def moved_owner():
                source.write_text("operator +(a:owned<i32>,b:i32)->i32{let r=&a;return *r+b;}fn main()->i32{let a=own(20);let n=move a+22;return move a+22;}", encoding="utf-8")
                result = invoke("check")
                assert result.returncode == 1 and "live unborrowed owner" in result.stdout + result.stderr, result.stdout + result.stderr
            test("operator invocation preserves move checking", moved_owner)
        def project():
            source.write_text("fn combine(a:i32,b:i32)->i32{return a+b;}fn main()->i32{return 20@22;}", encoding="utf-8")
            (work / "rules.stx").write_text(extension.read_text(), encoding="utf-8")
            (work / "demo.stx").write_bytes((ROOT / "examples/emergence/demo.stx").read_bytes())
            (work / "Naru.toml").write_text('[package]\nname="operator-project"\nversion="0.1.0"\nentry="main.nru"\n[exports]\noperator_extension="rules.stx"\ndemo="demo.stx"\n[dependencies.std]\npath='+json.dumps(str(ROOT / "dialects"))+'\npackage="naru-stdlib"\nversion="^0.2.0"\n[language]\ndialects=["std/standard","std/money","demo","operator_extension"]\nunit="program"\nrelation="standard.emit_program"\n[backend]\ntarget="exe"\n', encoding="utf-8")
            resolved = execute([str(ROOT / "target/naru.exe"), "resolve", "--project", str(work)], cwd=work, env=env)
            assert resolved.returncode == 0, resolved.stdout + resolved.stderr
            built = execute([str(compiler), "build", "--project", str(work), "--locked", "-o", str(output)], cwd=work, env=env, timeout=90)
            assert built.returncode == 0, built.stdout + built.stderr
            assert execute([str(output)], cwd=work, env=env).returncode == 42
        test("project references compose additional operator rules", project)
        if args.frozen:
            def changed_frozen():
                changed = work / "base.stx"
                changed.write_text((ROOT / "dialects/base.stx").read_text() + "\n// changed frozen module\n", encoding="utf-8")
                result = invoke("check", "--rules", changed)
                assert result.returncode == 1 and "differs from frozen dialect" in result.stdout + result.stderr, result.stdout + result.stderr
            test("a dynamic extension cannot mutate a frozen module", changed_frozen)
            def next_generation():
                generated = work / "next.vyx"
                result = execute([str(compiler), "freeze", "--rules", str(extension), "-o", str(generated)], cwd=work, env=env, timeout=90)
                assert result.returncode == 0, result.stdout + result.stderr
                text = generated.read_text()
                assert "operator_extension.mixed" in text and "specialized_load" in text and "specialized_effect_count" in text
            test("the augmented group generates a next-generation compiler", next_generation)
    passed = sum(check["passed"] for check in checks)
    report = ROOT / "target" / ("operators-frozen-tests.json" if args.frozen else "operators-tests.json")
    report.write_text(json.dumps({"compiler":str(compiler),"checks":checks},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"{passed}/{len(checks)} operator checks passed")
    return int(passed != len(checks))

if __name__ == "__main__":
    raise SystemExit(main())
