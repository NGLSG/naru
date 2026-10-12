"""Native acceptance of composed language-library features and their boundaries."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = [
    ("nominal records, aliases, mutation and calls", (ROOT / "tests/fixtures/emergence/emergence-records.nru").read_text(), 42),
    ("generics, numeric evidence and range control", (ROOT / "tests/fixtures/emergence/emergence-generics.nru").read_text(), 42),
    ("generic option, mutable storage and exhaustive match", (ROOT / "tests/fixtures/emergence/emergence-match.nru").read_text(), 42),
    ("exclusive loan, write, end and cross-function move", (ROOT / "tests/fixtures/emergence/emergence-owned.nru").read_text(), 42),
    ("deferred ownership transfer and terminal branches", (ROOT / "tests/fixtures/emergence/emergence-defer.nru").read_text(), 42),
    ("dynamic array reads, writes and by-value calls", (ROOT / "tests/fixtures/emergence/emergence-array.nru").read_text(), 42),
    ("user enum with record payload and binders", (ROOT / "tests/fixtures/emergence/emergence-enum.nru").read_text(), 42),
    ("function values and higher-order call", (ROOT / "tests/fixtures/emergence/emergence-functions.nru").read_text(), 42),
    ("native closure environment", (ROOT / "tests/fixtures/emergence/emergence-closure.nru").read_text(), 42),
    ("generic scalar and owned identity", "fn id<T>(x:T)->T{return move x;} fn main()->i32 {let x=id<i32>(20);let y=id<owned<i32>>(own(22));let r=&y;let z=*r;end r;return x+z;}", 42),
    ("recursive generic instance", "fn count<T>(n:T)->T where T:Integer {if n==0 {return 42;}return count<T>(n-1);} fn main()->i32{return count<i32>(8);}", 42),
    ("result success payload", "fn make()->result<i32,i32>{return ok(42);} fn main()->i32{return match make(){ok(n)=>n,err(e)=>e};}", 42),
    ("result error payload", "fn make()->result<i32,i32>{return err(42);} fn main()->i32{return match make(){ok(n)=>n,err(e)=>e};}", 42),
    ("literal and catch-all match", "fn main()->i32{return match 8 {0=>0,7=>1,n=>n+34};}", 42),
    ("bool match coverage", "fn main()->i32{return match false {true=>0,false=>42};}", 42),
    ("nested record and pair", "struct P{x:i32;y:i32;} struct Q{p:P;n:i32;} fn main()->i32{let q=Q{n:1,p:P{x:20,y:22}};let p=pair(q.p.x,q.p.y);return p.first+p.second;}", 42),
    ("short circuit skips runtime division by zero", "fn bad()->bool{var z=0;return (1/z)==0;} fn main()->i32{if true||bad(){return 42;}else{return 1;}}", 42),
    ("shift signedness", "fn main()->i32{let n:u32=21;return (n<<1) as i32;}", 42),
    ("floating and index conversions", "fn main()->i32{let x:f64=42.5;let y=x as f32;let n=(y as i32) as index;return n as i32;}", 42),
    ("native vector construction and arithmetic", "fn main()->i32{let x:vector<3,i32>=vector{10,20,12};let y=x+x;return y[1]+2;}", 42),
    ("implicit loan end at branch scope", "fn take(x:owned<i32>)->i32{let r=&x;return *r;} fn main()->i32{let x=own(42);if true{let r=&x;let n=*r;}return take(move x);}", 42),
    ("loop loans restore state", "fn main()->i32{let x=own(42);var n=0;while n<3 {let r=&x;let y=*r;n=n+1;}let r=&x;return *r;}", 42),
    ("array temporary spill restores loop stack", "fn make()->array<3,i32>{return [1,2,3];} fn main()->i32{var i=0;var n=0;while i<100000{var j=1;n=n+make()[j];i=i+1;}return n-199958;}", 42),
    ("nested closure captures", "fn main()->i32{let x=20;let outer=fn[x](n:i32)->i32{let inner=fn[n,x](v:i32)->i32{return n+x+v;};return inner(2);};return outer(20);}", 42),
    ("closure capture snapshot", "fn main()->i32{var x=20;let f=fn[x](n:i32)->i32{return x+n;};x=0;return f(22);}", 42),
    ("closure in a match arm", "fn main()->i32{return match some(20){none=>0,some(x)=>(fn[x](n:i32)->i32{return x+n;})(22)};}", 42),
    ("direct function-value expression", "fn f(n:i32)->i32{return n+2;}fn main()->i32{return (fn f)(40);}", 42),
]
ERRORS = [
    ("duplicate record field", "struct P{x:i32;x:i32;}fn main()->i32{let p=P{x:1};return 0;}", "duplicate type field"),
    ("recursive by-value record", "struct P{p:P;}fn main()->i32{let p:P=0;return 0;}", "recursive value type"),
    ("duplicate initializer field", "struct P{x:i32;y:i32;}fn main()->i32{let p=P{x:1,x:2};return 0;}", "duplicate initializer field"),
    ("generic arity", "fn id<T>(x:T)->T{return x;}fn main()->i32{return id<i32,u32>(42);}", "generic type argument count"),
    ("failed generic capability", "fn f<T>(x:T)->T where T:Numeric{return x;}fn main()->i32{let x=f<bool>(true);return 0;}", "unsatisfied capability"),
    ("nonexhaustive option", "fn main()->i32{return match some(42){none=>0};}", "not exhaustive"),
    ("duplicate match", "fn main()->i32{return match 42{0=>0,0=>1,_=>42};}", "duplicate match arm"),
    ("unreachable match", "fn main()->i32{return match 42{_=>42,0=>1};}", "unreachable match arm"),
    ("break outside loop", "fn main()->i32{break;return 42;}", "break outside"),
    ("continue outside loop", "fn main()->i32{continue;return 42;}", "continue outside"),
    ("immutable record field", "struct P{x:i32;}fn main()->i32{let p=P{x:1};p.x=42;return 0;}", "mutable var"),
    ("static array bounds", "fn main()->i32{let a=[1,2];return a[2];}", "array index out of bounds"),
    ("immutable array write", "fn main()->i32{let a=[1,2];a[0]=42;return 0;}", "mutable array"),
    ("double move", "fn take(x:owned<i32>)->i32{let r=&x;return *r;}fn main()->i32{let x=own(42);let a=take(move x);return take(move x);}", "live unborrowed owner"),
    ("implicit owned copy", "fn main()->i32{let x=own(42);let y=x;return 0;}", "requires move or borrow"),
    ("shared unique conflict", "fn main()->i32{let x=own(42);let a=&x;let b=&mut x;return 0;}", "borrow conflicts"),
    ("move while borrowed", "fn main()->i32{let x=own(42);let r=&x;let y=move x;return 0;}", "live unborrowed owner"),
    ("ended loan", "fn main()->i32{let x=own(42);let r=&x;end r;return *r;}", "ended loan"),
    ("copied loan", "fn main()->i32{let x=own(42);let r=&x;let alias=r;end r;return *alias;}", "loan cannot be copied"),
    ("write through shared", "fn main()->i32{let x=own(42);let r=&x;*r=0;return 42;}", "shared borrow"),
    ("borrow escape", "fn f()->ref<i32>{let x=own(42);let r=&x;return r;}", "loan cannot be copied"),
    ("branch move join", "fn take(x:owned<i32>)->i32{let r=&x;return *r;}fn main()->i32{let x=own(42);if true{take(move x);}return take(move x);}", "live unborrowed owner"),
    ("loop ownership transfer", "fn take(x:owned<i32>)->i32{let r=&x;return *r;}fn main()->i32{let x=own(42);while true{take(move x);}return 0;}", "loop changes ownership"),
    ("affine aggregate needs partial move contract", "struct P{x:owned<i32>;}fn main()->i32{return 42;}", "partial-move contract"),
    ("closure loan capture", "fn main()->i32{let x=own(42);let r=&x;let f=fn[r]()->i32{return *r;};return f();}", "partial-move contract"),
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true")
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    env = dict(os.environ); env["PATH"] = ""
    rules = [] if args.frozen else ["--rules", str(ROOT / "dialects/standard.stx")]
    results = []
    with tempfile.TemporaryDirectory(prefix="naru-emergence-") as directory:
        work = Path(directory); source = work / "main.nru"; output = work / "main.exe"
        def invoke(*argv):
            return execute([str(compiler), *map(str, argv), *rules, "--unit", "program", "--relation", "standard.emit_program"], cwd=ROOT, env=env, timeout=60)
        def test(label, action):
            try:
                action(); results.append({"name": label, "passed": True}); print("PASS " + label)
            except (AssertionError, OSError) as error:
                results.append({"name": label, "passed": False, "error": str(error)}); print(f"FAIL {label}: {error}")
        for name, program, expected in PROGRAMS:
            for level in ("0", "2"):
                def native(program=program, expected=expected, level=level):
                    source.write_text(program, encoding="utf-8")
                    built = invoke("build", source, "--target", "exe", "--opt-level", level, "-o", output)
                    assert built.returncode == 0, built.stdout + built.stderr
                    ran = execute([str(output)], cwd=work, env=env, timeout=60)
                    assert ran.returncode == expected, ran
                test(f"{name} O{level}", native)
        for name, program, message in ERRORS:
            def reject(program=program, message=message):
                source.write_text(program, encoding="utf-8"); output.write_bytes(b"preserved")
                result = invoke("build", source, "--target", "exe", "-o", output)
                assert result.returncode in (1,2) and message in result.stdout + result.stderr, result.stdout + result.stderr
                assert output.read_bytes() == b"preserved"
            test(name, reject)
        for level in ("0","2"):
            def trap(level=level):
                source.write_text("fn main()->i32{let a=[1,2];var i=2;return a[i];}",encoding="utf-8")
                built=invoke("build",source,"--target","exe","--opt-level",level,"-o",output)
                assert built.returncode==0,built.stdout+built.stderr
                assert execute([str(output)],cwd=work,env=env).returncode!=0
            test("dynamic array bounds trap O"+level,trap)
        for level in ("0","2"):
            def cleanups(level=level):
                source.write_text('extern "C"{fn puts(s:*char)->i32;}fn f()->i32{defer puts("outer");for i in 0 .. 3{defer puts("loop");if i==0{continue;}if i==1{break;}}if true{defer puts("branch");return 42;}else{return 1;}}fn main()->i32{return f();}',encoding="utf-8")
                built=invoke("build",source,"--target","exe","--runtime","crt-static","--opt-level",level,"-o",output)
                assert built.returncode==0,built.stdout+built.stderr
                ran=execute([str(output)],cwd=work,env=env)
                assert ran.returncode==42 and ran.stdout.splitlines()==["loop","loop","branch","outer"],ran
            test("defer LIFO on continue break and return O"+level,cleanups)
        for label,program,expected in [
            ("defer snapshots a function value",'extern "C"{fn puts(s:*char)->i32;}fn a()->void{puts("a");}fn b()->void{puts("b");}fn main()->i32{let f=fn a;defer f();let f=fn b;return 42;}',["a"]),
            ("defer invokes a captured closure",'extern "C"{fn puts(s:*char)->i32;}fn main()->i32{let x=20;let f=fn[x]()->void{if x==20{puts("closure");}else{puts("bad");}};defer f();return 42;}',["closure"]),
        ]:
            def deferred_callable(program=program,expected=expected):
                source.write_text(program,encoding="utf-8")
                built=invoke("build",source,"--target","exe","--runtime","crt-static","-o",output)
                assert built.returncode==0,built.stdout+built.stderr
                ran=execute([str(output)],cwd=work,env=env)
                assert ran.returncode==42 and ran.stdout.splitlines()==expected,ran
            test(label,deferred_callable)
        def project():
            report=work/"report.json"
            built=execute([str(compiler),"build","--project",str(ROOT/"examples/emergence"),"--locked","--report",str(report),"-o",str(output)],cwd=work,env=env,timeout=60)
            assert built.returncode==0,built.stdout+built.stderr
            data=json.loads(report.read_text()); assert data["processes_spawned"]==0
            ran=execute([str(output)],cwd=work,env=env)
            assert ran.returncode==42 and ran.stdout.strip()=="Naru: composed rules complete",ran
        test("project combines custom rules with the full standard group",project)
        if not args.frozen:
            protocol=ROOT/"tests/fixtures/emergence/protocol.stx"
            for label,expr,expected in [
                ("additive peers keep registration order",'collect("protocol.claims",["yes"])','["first", "second"]'),
                ("collection falls back when no peer matches",'collect("protocol.claims",["no"])','["fallback"]'),
                ("iterative generic left fold",'list.fold("protocol.combine",[1,2,3],[])','[1, 2, 3]'),
                ("topological stage composition",'pipeline.run([])','["B", "A"]'),
                ("overlapping resource join is disjoint",'resources.join_value(resources.MaybeMoved(0),resources.MaybeMoved(0))','resources.MaybeMoved(0)'),
            ]:
                def evaluate(expr=expr,expected=expected):
                    actual=execute([str(compiler),"eval","--rules",str(protocol),"--rules",str(ROOT/"dialects/types.stx"),"--rules",str(ROOT/"dialects/pipeline.stx"),"--rules",str(ROOT/"dialects/constraints.stx"),"--rules",str(ROOT/"dialects/resources.stx"),"--expr",expr],cwd=ROOT,env=env)
                    assert actual.returncode==0 and actual.stdout.strip()==expected,actual.stdout+actual.stderr
                test(label,evaluate)
            def ambiguity():
                actual=execute([str(compiler),"eval","--rules",str(protocol),"--rules",str(ROOT/"dialects/types.stx"),"--rules",str(ROOT/"dialects/pipeline.stx"),"--rules",str(ROOT/"dialects/constraints.stx"),"--rules",str(ROOT/"dialects/resources.stx"),"--expr",'protocol.claims("yes")'],cwd=ROOT,env=env)
                assert actual.returncode==1 and "ambiguous effect" in actual.stdout+actual.stderr
            test("ordinary peer calls still reject ambiguity",ambiguity)
            def field_solver():
                actual=execute([str(compiler),"eval","--rules",str(protocol),"--rules",str(ROOT/"dialects/types.stx"),"--rules",str(ROOT/"dialects/pipeline.stx"),"--rules",str(ROOT/"dialects/constraints.stx"),"--rules",str(ROOT/"dialects/resources.stx"),"--expr",'types.solve([constraints.HasField(constraints.Record([constraints.Field("x",types.Signed(32)),constraints.Field("y",types.Unsigned(8))]),"x",types.Signed(32))],env.empty())'],cwd=ROOT,env=env)
                assert actual.returncode==0 and "Solved" in actual.stdout,actual.stdout+actual.stderr
            test("first field of a multi-field structural constraint",field_solver)
    report = ROOT / "target" / ("emergence-frozen-tests.json" if args.frozen else "emergence-tests.json")
    report.write_text(json.dumps({"compiler":str(compiler),"checks":results},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    passed=sum(item["passed"] for item in results)
    print(f"{passed}/{len(results)} composed-language checks passed")
    return int(passed != len(results))

if __name__ == "__main__":
    raise SystemExit(main())
