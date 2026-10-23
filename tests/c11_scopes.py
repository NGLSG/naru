"""C11 contextual declaration scopes, compared with Clang, bounded and serial."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from native_process import execute
from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("block_typedef", "int main(void){typedef int Number;Number x=42;return x;}", None),
    ("nested_typedef_shadow", "typedef int T;int main(void){int n=sizeof(T);{typedef long long T;T x=0;n+=sizeof(x);}T x=30;return n+x;}", None),
    ("ordinary_shadow_initializer", "typedef long long T;int main(void){int T=sizeof(T);return T+38;}", None),
    ("ordinary_shadow_parentheses", "typedef int T;int main(void){int T=2;return (T)+40;}", None),
    ("typedef_named_variable", "typedef int T;int main(void){T T=42;return T;}", None),
    ("comma_declaration_visibility", "typedef long long T;int main(void){int T=sizeof(T),next=T+38;return next;}", None),
    ("comma_typedef_visibility", "int main(void){typedef int T,A[sizeof(T)];A a;return sizeof(a)+26;}", None),
    ("parameter_masks_typedef_in_body", "typedef long long T;int f(int T){return sizeof(T)+38;}int main(void){return f(7);}", None),
    ("prototype_scope_restored", "typedef int T;int f(int T);T answer=42;int f(int T){return answer;}int main(void){return f(7);}", None),
    ("parameter_hides_later_typedef", "typedef int T;int f(int T,T x);int main(void){return 42;}", "cannot parse"),
    ("duplicate_parameter", "int f(int x,int x){return 42;}int main(void){return f(1,2);}", "duplicate C parameter"),
    ("compatible_typedef_redeclaration", "int main(void){typedef int T;typedef int T;T x=42;return x;}", None),
    ("incompatible_typedef_redeclaration", "int main(void){typedef int T;typedef long long T;return 42;}", "incompatible C local typedef"),
    ("same_block_namespace_conflict", "int main(void){int T=7;typedef int T;return 42;}", "incompatible C local typedef"),
    ("typedef_cannot_read_outer_object", "int T=7;int main(void){typedef int T;return T;}", "C typedef name is not an expression"),
    ("block_type_does_not_escape", "int main(void){{typedef int T;T x=42;}T x=42;return x;}", "cannot parse"),
    ("for_scope_masks_and_restores", "typedef long long T;int main(void){int n=0;for(int T=0;T<3;T++){n+=sizeof(T);}T answer=30;return n+answer;}", None),
    ("for_static_rejected", "int main(void){for(static int i=0;i<1;i++){}return 42;}", "C for initializer declaration requires automatic objects"),
    ("for_extern_rejected", "int main(void){for(extern int i;0;){}return 42;}", "C for initializer declaration requires automatic objects"),
    ("for_typedef_rejected", "int main(void){for(typedef int T;0;){}return 42;}", "C for initializer declaration requires automatic objects"),
    ("for_function_rejected", "int main(void){for(int f(void);0;){}return 42;}", "C for initializer cannot declare a function"),
    ("for_later_function_rejected", "int main(void){for(int i=0,f(void);0;){}return 42;}", "C for initializer cannot declare a function"),
    ("for_function_alias_rejected", "typedef int Fn(void);int main(void){for(Fn f;0;){}return 42;}", "C for initializer cannot declare a function"),
    ("if_else_block_types", "int main(void){int n=0;if(1){typedef int T;T x=42;n=x;}else{typedef long long T;T x=7;n=x;}return n;}", None),
    ("while_block_type", "int main(void){int n=0;while(n<1){typedef int T;T x=42;n=x;}return n;}", None),
    ("do_block_type", "int main(void){int n=0;do{typedef int T;T x=42;n=x;}while(n<1);return n;}", None),
    ("label_block_type", "int main(void){goto next;next:{typedef int T;T x=42;return x;}}", None),
    ("switch_block_types", "int main(void){int n=0;switch(1){case 1:{typedef int T;T x=42;n=x;break;}default:n=7;}return n;}", None),
    ("function_pointer_alias", "int f(int x){return x+1;}typedef int (*Fn)(int);int main(void){Fn p=f;return p(41);}", None),
    ("grouped_function_declarator", "int (f)(int x){return x+1;}int main(void){return f(41);}", None),
    ("file_namespace_conflict", "typedef int T;int T;int main(void){return 42;}", "C ordinary identifier conflicts with typedef"),
    ("declspec_grouped_objects", '__declspec(deprecated("old")) int value=42,other=0;int main(void){return value;}', None),
    ("declspec_nested_function", '__declspec(noalias) __declspec(deprecated("old")) static int answer(void){return 42;}int main(void){return answer();}', None),
    ("declspec_invalid_argument", '__declspec(deprecated(42)) int value=42;int main(void){return value;}', "cannot parse c11.item"),
    ("sdk_stdlib", "#include <stdlib.h>\nint main(void){int *p=malloc(sizeof(*p));if(!p)return 1;*p=42;int n=*p;free(p);return n;}", None),
    ("sdk_limits", "#include <limits.h>\nint main(void){if(INT_MAX>42 && ULLONG_MAX>42)return 42;return 1;}", None),
    ("sdk_stdarg", "#include <stdarg.h>\nint sum(int n,...){va_list a;va_start(a,n);int result=0;for(int i=0;i<n;i++)result+=va_arg(a,int);va_end(a);return result;}int main(void){return sum(2,20,22);}", None),
    ("static_assert_nested_casts", '_Static_assert((int)(20.5)+(int)(22.5)==42,"cast");int main(void){return 42;}', None),
    ("sizeof_function_pointer_type", "_Static_assert(sizeof(int(*)(int))==sizeof(void*),\"pointer\");int main(void){return 42;}", None),
    ("aligned_local_storage", "int main(void){_Alignas(16) int value=42;if((unsigned long long)&value%16==0)return value;return 1;}", None),
    ("aligned_comma_pointer_array", "int main(void){int value=42;_Alignas(16) int *p=&value,a[2]={20,22};if((unsigned long long)&p%16==0 && (unsigned long long)a%16==0 && sizeof(p)==sizeof(void*) && sizeof(a)==2*sizeof(int) && sizeof(*p)==sizeof(int) && *p==42)return a[0]+a[1];return 1;}", None),
    ("aligned_type_name", "typedef long long Wide;int main(void){_Alignas(Wide) int value=42;if((unsigned long long)&value%_Alignof(Wide)==0 && sizeof(value)==sizeof(int))return value;return 1;}", None),
    ("aligned_type_policy_survives_comma_shadow", "typedef long long Wide;int main(void){_Alignas(Wide) int Wide=20,answer=22;if((unsigned long long)&Wide%8==0 && (unsigned long long)&answer%8==0)return Wide+answer;return 1;}", None),
    ("aligned_ordinary_shadow_rejected", "typedef long long Wide;int main(void){int Wide=16;_Alignas(Wide) int value=42;return value;}", "C context requires an integer constant expression"),
    ("aligned_for_ordinary_shadow_rejected", "typedef long long Wide;int main(void){int Wide=16;for(_Alignas(Wide) int i=0;i<1;i++){}return 42;}", "C context requires an integer constant expression"),
    ("aligned_comma_hides_type_in_initializer", "typedef long long Wide;int main(void){_Alignas(16) int Wide=16,value=_Alignof(Wide);return 42;}", "cannot parse"),
    ("aligned_merged_specifiers", "int main(void){_Alignas(0) _Alignas(16) _Alignas(32) int value=42;if((unsigned long long)&value%32==0)return value;return 1;}", None),
    ("aligned_static_local", "int next(void){_Alignas(32) static int value=40;value++;if((unsigned long long)&value%32!=0)return 1;return value;}int main(void){next();return next();}", None),
    ("aligned_for_object", "int main(void){for(_Alignas(16) int i=0;i<1;i++){if((unsigned long long)&i%16==0)return 42;}return 1;}", None),
    ("aligned_weaker_rejected", "int main(void){_Alignas(2) long long value=42;return value;}", "C alignment specifier weakens the natural object alignment"),
    ("aligned_non_power_rejected", "int main(void){_Alignas(3) int value=42;return value;}", "C alignment must be zero or a power of two"),
    ("aligned_non_integer_constant_rejected", "int main(void){_Alignas((int)(1.0+1.0)) int value=42;return value;}", "C context requires an integer constant expression"),
    ("aligned_typedef_rejected", "int main(void){_Alignas(16) typedef int T;return 42;}", "C alignment specifier cannot apply to a typedef"),
    ("aligned_for_static_rejected", "int main(void){for(_Alignas(16) static int i=0;i<1;i++){}return 42;}", "C for initializer declaration requires automatic objects"),
    ("aligned_for_typedef_rejected", "int main(void){for(_Alignas(16) typedef int T;0;){}return 42;}", "C alignment specifier cannot apply to a typedef"),
    ("aligned_for_function_rejected", "int main(void){for(_Alignas(16) int f(void);0;){}return 42;}", "C alignment specifier cannot apply to a function declaration"),
]

# Clang 22 accepts a later function declarator in this mixed for declaration.
# C11 N1570 6.8.5p3 requires every declared identifier to denote an automatic
# or register object. Keep this standards regression even when the oracle
# does not diagnose it, and record the disagreement in the report.
REFERENCE_DIAGNOSTIC_GAPS = {"for_later_function_rejected": "C11 N1570 6.8.5p3"}
REFERENCE_OPTIONS = {name: ["-fms-extensions"] for name, _, _ in CASES if name.startswith("declspec_")}


def fingerprints(compiler: Path) -> dict[str, str]:
    result = {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in c11_rule_inputs()}
    result["compiler:" + str(compiler)] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    backend = compiler.parent / "naru_mlir_backend.dll"
    if backend.is_file():
        result["backend:" + str(backend)] = hashlib.sha256(backend.read_bytes()).hexdigest()
    result["test:" + str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append")
    parser.add_argument("--opt", action="append", choices=["0", "2"])
    parser.add_argument("--reference", type=Path, default=Path("D:/LLVM/bin/clang.exe"))
    parser.add_argument("--compiler", type=Path, default=ROOT / "target/naru.exe")
    parser.add_argument("--frozen", action="store_true", help="Use C11 rules frozen in the selected compiler")
    parser.add_argument("--report", type=Path, default=ROOT / "target/c11-scopes.json")
    parser.add_argument("--timeout", type=float, default=20)
    args = parser.parse_args()
    args.compiler = args.compiler.resolve()
    frozen = validate_frozen(args.compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    if args.case and set(args.case) - {case[0] for case in CASES}:
        parser.error("Unknown scope case")
    work = ROOT / "target/c11-scopes"
    work.mkdir(parents=True, exist_ok=True)
    before = fingerprints(args.compiler)
    results = []
    for name, content, reject in CASES:
        if args.case and name not in args.case:
            continue
        source = work / (name + ".c")
        source.write_text(content + "\n", encoding="utf-8")
        for opt in args.opt or ["0", "2"]:
            record = dict(name=name, opt=opt, passed=False)
            try:
                ref_command = [str(args.reference), "-std=c11", "-pedantic-errors", *REFERENCE_OPTIONS.get(name, [])]
                if reject:
                    ref_command += ["-fsyntax-only", str(source)]
                else:
                    reference_exe = work / (name + "-clang-O" + opt + ".exe")
                    ref_command += ["-O" + opt, "-fuse-ld=lld", "-fms-runtime-lib=static", str(source), "-o", str(reference_exe)]
                reference = subprocess.run(ref_command, cwd=work, capture_output=True, text=True, timeout=args.timeout)
                reference_validated = (reference.returncode != 0) == bool(reject)
                if not reference_validated and reject and name in REFERENCE_DIAGNOSTIC_GAPS:
                    record["reference_diagnostic_gap"] = REFERENCE_DIAGNOSTIC_GAPS[name]
                else:
                    assert reference_validated, reference.stdout + reference.stderr
                record["reference_exit"] = reference.returncode
                output = work / (name + "-O" + opt + ".exe")
                budget = "100000000" if name.startswith("sdk_") else "10000000"
                command = [str(args.compiler), "build", str(source)] + ([] if args.frozen else ["--rules", str(ROOT / "dialects/c11.stx")]) + [
                           "--frontend", "c11.frontend", "--unit", "program", "--relation", "c11.emit_program",
                           "--runtime", "crt-static", "--target", "exe", "--opt-level", opt,
                           "--rule-depth", "1024", "--rule-budget", budget, "--parse-budget", budget, "-o", str(output)]
                build = execute(command, cwd=ROOT, env=dict(os.environ, PATH=""), timeout=args.timeout, memory_limit=512 * 1024**2)
                record.update(compile_exit=build.returncode, compile_seconds=round(build.elapsed_seconds, 4), peak_commit_bytes=build.peak_memory_bytes)
                if reject:
                    assert build.returncode != 0, "Invalid C accepted"
                    assert reject in build.stdout + build.stderr, build.stdout + build.stderr
                else:
                    assert build.returncode == 0, build.stdout + build.stderr
                    native = execute([str(output)], cwd=work, timeout=3, memory_limit=64 * 1024**2)
                    oracle = execute([str(reference_exe)], cwd=work, timeout=3)
                    assert (native.returncode, native.stdout) == (42, ""), repr((native.returncode, native.stdout))
                    assert (native.returncode, native.stdout) == (oracle.returncode, oracle.stdout), "Clang disagreement"
                record.update(passed=True, reference_validated=reference_validated)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                record["error"] = str(error)[-5000:]
            results.append(record)
            print(("PASS " if record["passed"] else "FAIL ") + name + " O" + opt +
                  ("" if record["passed"] else ": " + record["error"][:500]), flush=True)
    after = fingerprints(args.compiler)
    unchanged = after == before
    if args.frozen:
        unchanged = unchanged and frozen == validate_frozen(args.compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    rules_unchanged = all(after.get(key) == value for key, value in before.items() if key.startswith("dialects/"))
    report = dict(generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                  compiler=str(args.compiler), frozen=args.frozen, fingerprints=before, frozen_provenance=frozen,
                  compiler_sha256=hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
                  test_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  rule_sha256={key: value for key, value in before.items() if key.startswith("dialects/")},
                  process_limit=1, memory_limit_mib=512, rules_unchanged=rules_unchanged, inputs_unchanged=unchanged,
                  passed=unchanged and bool(results) and all(row["passed"] for row in results), results=results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
