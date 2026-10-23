"""C11 aggregate expression value categories and full-expression temporaries.

Valid fixtures consume all temporary array pointers within their full
expression. No pointer escapes past that boundary; no temporary array is
modified. Non-lvalue scalar-member assignment is a required diagnostic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from c11_conformance import main as conformance_main, fingerprints
from frozen_snapshot import validate_frozen
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def valid(name: str, source: str, clause: str = '6.2.4p8;6.5.2.3p3') -> dict:
    return dict(id=name, feature='lifetime', clause=clause, source=source, exit=42)


CASES = [
    dict(id='cast-anonymous-record-rejected', feature='expressions', clause='6.5.4p2',
        source='typedef struct {int n;} S;int main(void){S s={42};return ((S)s).n;}', reject='C cast requires a scalar'),
    dict(id='cast-named-record-rejected', feature='expressions', clause='6.5.4p2',
        source='struct S{int n;};int main(void){struct S s={42};return ((struct S)s).n;}', reject='C cast requires a scalar'),
    dict(id='cast-union-rejected', feature='expressions', clause='6.5.4p2',
        source='typedef union{int n;} U;int main(void){U u={42};return ((U)u).n;}', reject='C cast requires a scalar'),
    dict(id='cast-aggregate-operand-rejected', feature='expressions', clause='6.5.4p2',
        source='typedef struct{int n;} S;int main(void){S s={42};return (int)s;}', reject='C cast requires a scalar'),
    dict(id='cast-void-operand-rejected', feature='expressions', clause='6.5.4p2',
        source='int main(void){return (int)((void)42);}', reject='C cast requires a scalar'),
    dict(id='cast-pointer-to-floating-rejected', feature='expressions', clause='6.5.4p4',
        source='int main(void){int n=42;return (int)((double)&n);}', reject='cannot convert between pointer and floating'),
    dict(id='cast-floating-to-pointer-rejected', feature='expressions', clause='6.5.4p4',
        source='int main(void){int*p=(int*)42.0;return 42;}', reject='cannot convert between pointer and floating'),
    valid('void-cast-aggregate-evaluates-once', 'int calls;struct S{int n;};struct S make(void){++calls;struct S s={42};return s;}int main(void){(void)make();return calls==1?42:1;}', '6.5.4p2;6.3.2.2'),
    valid('void-cast-scalar-preserves-effects', 'int main(void){int n=0;(void)(n=42);return n;}', '6.5.4p2;6.3.2.2'),
    valid('qualified-void-cast-aggregate', 'struct S{int n;};int main(void){struct S s={42};(const void)s;return 42;}', '6.5.4p2;6.5.4 footnote 104'),
    valid('cast-qualified-scalar-typedef', 'typedef int I;int main(void){return (const volatile I)42;}', '6.5.4p2;6.5.4 footnote 104'),
    valid('cast-qualified-pointer-typedef', 'typedef int*P;int main(void){int n=42;P p=(const volatile P)&n;return *p;}', '6.5.4p2;6.5.4 footnote 104'),
    # Pointer/integer maps are implementation-defined. These cases compare
    # only the selected Windows x64 zero mapping with the target reference.
    valid('bool-to-null-pointer-cast', 'int main(void){_Bool b=0;int*p=(int*)b;return p==0?42:1;}', '6.3.2.3p5;6.5.4p2'),
    valid('char-to-null-pointer-cast', 'int main(void){char c=0;int*p=(int*)c;return p==0?42:1;}', '6.3.2.3p5;6.5.4p2'),
    valid('enum-to-null-pointer-cast', 'enum E{N=0};int main(void){enum E e=N;int*p=(int*)e;return p==0?42:1;}', '6.3.2.3p5;6.5.4p2'),
    valid('null-pointer-to-enum-cast', 'enum E{N=0};int main(void){enum E e=(enum E)(int*)0;return e==N?42:1;}', '6.3.2.3p6;6.5.4p2'),
    valid('null-pointer-to-char-cast', 'int main(void){char c=(char)(int*)0;return c==0?42:1;}', '6.3.2.3p6;6.5.4p2'),
    valid('pointer-to-bool-tests-nullness', 'int main(void){int n=42;_Bool b=(_Bool)&n;return b?42:1;}', '6.3.1.2p1;6.5.4p2'),
    valid('record-fallthrough-value-discarded', 'int calls;struct S{int n;};struct S fall(void){++calls;}int main(void){fall();return calls==1?42:1;}', '6.9.1p12'),
    valid('union-fallthrough-value-discarded', 'int calls;union U{int n;double d;};union U fall(void){++calls;}int main(void){fall();return calls==1?42:1;}', '6.9.1p12'),
    valid('returned-record-scalar-member', 'struct S{int n;};struct S make(void){struct S s={42};return s;}int main(void){return make().n;}', '6.5.2.3p3'),
    valid('aggregate-two-temporaries-one-expression', 'struct S{int a[1];};struct S make(int n){struct S s={{n}};return s;}int sum(const int*a,const int*b){return a[0]+b[0];}int main(void){return sum(make(20).a,make(22).a);}'),
    valid('assignment-result-array-temporary', 'struct S{int a[1];};int main(void){struct S a={{42}},b={{0}};return (b=a).a[0];}', '6.2.4p8;6.5.16p3'),
    valid('conditional-result-array-temporary', 'struct S{int a[1];};int main(void){struct S a={{42}},b={{0}};return (1?a:b).a[0];}', '6.2.4p8;6.5.15p6'),
    dict(id='nonlvalue-record-member-assignment', feature='lifetime', clause='6.5.16p2;6.5.2.3p3',
        source='struct S{int n;};struct S make(void){struct S s={0};return s;}int main(void){make().n=42;return 0;}',
        reject='modifiable lvalue'),
    dict(id='address-of-nonlvalue-scalar-member', feature='lifetime', clause='6.5.3.2p1;6.5.2.3p3',
        source='struct S{int n;};struct S make(void){struct S s={42};return s;}int main(void){int *p=&make().n;return *p;}',
        reject='modifiable lvalue'),
    valid('sizeof-array-result-does-not-call', 'int calls;struct S{int a[3];};struct S make(void){++calls;struct S s={{1,2,3}};return s;}int main(void){int size=sizeof(make().a);return calls==0 && size==3*sizeof(int) ? 42:1;}', '6.5.3.4p2'),
    valid('sizeof-scalar-result-does-not-call', 'int calls;struct S{int n;};struct S make(void){++calls;struct S s={42};return s;}int main(void){int size=sizeof(make().n);return calls==0 && size==sizeof(int) ? 42:1;}', '6.5.3.4p2'),
    valid('comma-result-array-temporary', 'int calls;struct S{int a[1];};struct S make(int n){++calls;struct S s={{n}};return s;}int main(void){int n=(make(1),make(42)).a[0];return n==42 && calls==2 ? 42:1;}', '6.2.4p8;6.5.17p2'),
    valid('comma-result-scalar-member', 'int calls;struct S{int n;};struct S make(int n){++calls;struct S s={n};return s;}int main(void){int n=(make(1),make(42)).n;return n==42 && calls==2 ? 42:1;}', '6.5.2.3p3;6.5.17p2'),
    valid('scalar-result-evaluates-once', 'int calls;struct S{int n;};struct S make(void){++calls;struct S s={42};return s;}int main(void){int n=make().n;return n==42 && calls==1 ? 42:1;}', '6.5.2.3p3'),
    valid('nested-record-array-temporary', 'struct A{int a[1];};struct B{struct A b;};struct B make(void){struct B s={{{42}}};return s;}int main(void){return make().b.a[0];}'),
    valid('address-temporary-array-element-within-call', 'struct S{int a[1];};struct S make(void){struct S s={{42}};return s;}int read(const int *p){return *p;}int main(void){return read(&make().a[0]);}'),
    valid('returned-union-active-array-temporary', 'union U{int a[1];int n;};union U make(void){union U u={.a={42}};return u;}int main(void){return make().a[0];}'),
    valid('generic-array-result-does-not-call', 'int calls;struct S{int a[1];};struct S make(void){++calls;struct S s={{0}};return s;}int main(void){int n=_Generic(make().a,int*:42,default:1);return n==42 && calls==0 ? 42:1;}', '6.5.1.1p3'),
    valid('identical-call-sites-have-distinct-temporaries', 'int calls=18;struct S{int a[1];};struct S make(void){calls+=2;struct S s={{calls}};return s;}int sum(const int*a,const int*b){return a[0]+b[0];}int main(void){return sum(make().a,make().a);}'),
    valid('temporary-storage-isolated-by-call-frame', 'struct S{int a[1];};struct S make(int n){struct S s={{n}};return s;}int rec(const int *p,int depth){if(depth==0)return p[0];return p[0]+rec(make(1).a,depth-1);}int main(void){return rec(make(39).a,3);}'),
    valid('loop-consumes-before-full-expression-ends', 'int calls;struct S{int a[1];};struct S make(int n){++calls;struct S s={{n}};return s;}int read(const int *p){return p[0];}int main(void){int sum=0;for(int i=1;i<=5;i++)sum+=read(make(i).a);return sum==15 && calls==5 ? 42:1;}'),
    dict(**valid('volatile-scalar-lvalue-member', 'struct S{int pad;int n;};int main(void){volatile struct S s={20,22};int a=s.n;int b=s.n;return a+b-2;}', '6.5.2.3p3;6.7.3p7'), volatile_loads=2),
    dict(**valid('volatile-array-lvalue-members', 'struct S{int a[2];};int main(void){volatile struct S s={{20,22}};return s.a[0]+s.a[1];}', '6.5.2.3p3;6.7.3p7'), volatile_loads=2),
]


def main() -> int:
    argv = list(sys.argv[1:])
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    options.add_argument('--report', type=Path, default=ROOT/'target/c11-temporaries.json')
    options.add_argument('--frozen', action='store_true')
    options.add_argument('--case', action='append')
    options.add_argument('--opt', action='append', choices=['0','2'])
    settings, _ = options.parse_known_args(argv)
    compiler = settings.compiler.resolve()
    source_path = Path(__file__).resolve()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    (ROOT/'target').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c11-temporaries-', dir=ROOT/'target') as generated:
        manifest = Path(generated)/'cases.json'
        manifest.write_text(json.dumps(dict(format=1, target='windows-x86_64-llp64',
            full_conformance_claimed=False, cases=CASES), indent=2)+'\n', encoding='utf-8')
        if '--reference' not in argv and Path('D:/LLVM/bin/clang.exe').exists():
            argv = ['--reference','D:/LLVM/bin/clang.exe',*argv]
        status = conformance_main(['--probe-manifest',str(manifest),
            '--report',str(settings.report),*argv])
        report = json.loads(settings.report.read_text(encoding='utf-8'))
        before = fingerprints(compiler,manifest)
        frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if settings.frozen else None
        work = Path(generated)
        common = ([] if settings.frozen else ['--rules',str(ROOT/'dialects/c11.stx')])+[
            '--frontend','c11.frontend','--entry','c11.item','--unit','program',
            '--relation','c11.emit_program','--rule-depth','1024',
            '--rule-budget','100000000','--parse-budget','100000000']
        for case in CASES:
            if 'volatile_loads' not in case or (settings.case and case['id'] not in settings.case):
                continue
            for opt in settings.opt or ['0','2']:
                record = dict(id=case['id']+'-volatile-IR', clause=case['clause'], opt=opt, passed=False)
                source = work/'volatile.c'
                output = work/('volatile-O'+opt+'.mlir')
                source.write_text(case['source']+'\n', encoding='utf-8')
                try:
                    built = execute([str(compiler),'build',str(source),*common,'--opt-level',opt,
                        '--target','mlir','-o',str(output)],cwd=work,env=dict(os.environ,PATH=''),
                        timeout=30,memory_limit=512*1024**2)
                    assert built.returncode==0, built.stdout+built.stderr
                    text = output.read_text(encoding='utf-8')
                    # A runtime value alone cannot prove a volatile access.
                    # Demand both actual i32 member loads after optimization.
                    loads = re.findall(r'\bllvm\.load\s+volatile\b[^\n]*->\s*i32\b',text)
                    assert len(loads)==case['volatile_loads'], text
                    record.update(passed=True, volatile_loads=len(loads))
                except (AssertionError,OSError) as error:
                    record['error']=str(error)
                report['results'].append(record)
                print(('PASS ' if record['passed'] else 'FAIL ')+record['id']+' O'+opt+
                    (': '+record['error'] if not record['passed'] else ''),flush=True)
        unchanged = before==fingerprints(compiler,manifest)
        if settings.frozen:
            unchanged = unchanged and frozen==validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    report['inputs_unchanged'] = report['inputs_unchanged'] and unchanged and source_hash==hashlib.sha256(source_path.read_bytes()).hexdigest()
    report['sha256'][source_path.relative_to(ROOT).as_posix()] = source_hash
    report['scope'] = 'defined aggregate expressions and constraint diagnostics; volatile member access also checked in optimized MLIR; no complete C11 claim'
    report['passed'] = sum(record['passed'] for record in report['results'])
    report['total'] = len(report['results'])
    settings.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['passed']}/{report['total']} aggregate temporary checks; inputs unchanged: {report['inputs_unchanged']}")
    return int(status!=0 or not report['inputs_unchanged'] or report['passed']!=report['total'])


if __name__=='__main__':
    raise SystemExit(main())
