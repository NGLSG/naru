"""C11 static compound objects and source address constants, against Clang.

All executed sources have defined behavior. Constraint examples are compiled
only. Expired automatic/temporary pointers and modifying temporary array
subobjects are UB, so they are deliberately absent from this acceptance set.
The shared runner enforces empty PATH, no compile subprocesses, O0/O2 and
unchanged inputs, and supports --frozen with the same source corpus.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile

from c11_conformance import main as conformance_main

ROOT = Path(__file__).resolve().parents[1]


def valid(name: str, source: str, clause: str = '6.5.2.5p5;6.6p7,p9') -> dict:
    return dict(id=name, feature='lifetime', clause=clause, source=source, exit=42)


def invalid(name: str, source: str, diagnostic: str,
            clause: str = '6.6p7,p9;6.7.9p4') -> dict:
    return dict(id=name, feature='lifetime', clause=clause, source=source,
                reject=diagnostic)


CASES = [
    valid('conditional-null-pointer-test', 'int a=20,b=22;int *p=(int*)0?&a:&b;int main(void){return *p+20;}'),
    valid('conditional-static-object-pointer-test', 'int a=42;int *p=&a?&a:0;int main(void){return *p;}'),
    valid('conditional-static-offset-pointer-test', 'int a[2]={20,22};int *p=(a+1)?a+1:0;int main(void){return *p+20;}'),
    valid('conditional-static-member-pointer-test', 'struct S{int n;};struct S s={42};int *p=&s.n?&s.n:0;int main(void){return *p;}'),
    valid('conditional-function-pointer-test', 'int f(void){return 42;}int(*p)(void)=f?f:0;int main(void){return p();}'),
    valid('conditional-string-pointer-test', 'char *p="x"?"x":0;int main(void){return *p==\'x\'?42:1;}'),
    valid('qualified-pointer-address-cast', 'int a=42;int *p=(int *const)&a;int main(void){return *p;}', '6.5.4p2;6.6p9'),
    valid('qualified-cast-in-ice', 'enum{N=(const int)42};int main(void){return N;}', '6.5.4p2;6.6p6'),
    valid('qualified-cast-in-static-arithmetic', 'int n=(const int)(20.5+21.5);int main(void){return n;}', '6.5.4p2;6.6p8'),
    invalid('conditional-pointer-test-cannot-read-stored-object', 'int a=42;int*p=&a;int*q=p?&a:0;int main(void){return *q;}', 'stored value'),
    valid('file-array-literal', 'int *p=(int[]){20,22};int main(void){return p[0]+p[1];}'),
    valid('file-scalar-literal-address', 'int *p=&(int){42};int main(void){return *p;}'),
    valid('file-record-literal', 'struct S{int x;int y;};struct S *p=&(struct S){.y=22,.x=20};int main(void){return p->x+p->y;}'),
    valid('file-distinct-literal-objects', 'int *p=(int[]){42};int *q=(int[]){42};int main(void){*p=20;return p!=q && *q==42 && *p==20 ? 42:1;}'),
    valid('file-object-persists-between-calls', 'int *p=(int[]){20};int bump(void){return ++*p;}int main(void){return bump()+bump()-1;}'),
    valid('file-nested-literal-addresses', 'struct S{int *p;int *q;};struct S *s=&(struct S){(int[]){20},&(int){22}};int main(void){return *s->p+*s->q;}'),
    valid('file-designated-array', 'int *p=(int[]){[2]=22,[0]=20};int main(void){return p[0]+p[2]+p[1];}'),
    valid('file-qualified-literal', 'const int *p=(const int[]){42};int main(void){return *p;}'),
    valid('named-array-decay', 'int a[2]={20,22};int *p=a;int main(void){return p[0]+p[1];}'),
    valid('array-address-add', 'int a[2]={20,22};int *p=a+1;int main(void){return *p+20;}'),
    valid('array-address-reversed-add', 'int a[2]={20,22};int *p=1+a;int main(void){return *p+20;}'),
    valid('array-address-subtract', 'int a[2]={20,22};int *p=(a+2)-1;int main(void){return *p+20;}'),
    valid('one-past-address', 'int a[2];int *p=a+2;int main(void){return p-a==2 ? 42:1;}'),
    valid('subscript-address', 'int a[2]={20,22};int *p=&a[1];int main(void){return *p+20;}'),
    valid('symmetric-subscript-address', 'int a[2]={20,22};int *p=&1[a];int main(void){return *p+20;}'),
    valid('nested-array-subscript-address', 'int a[2][2]={{1,20},{22,3}};int *p=&a[0][1];int *q=&a[1][0];int main(void){return *p+*q;}'),
    valid('member-address', 'struct S{char pad;int n;};struct S s={0,42};int *p=&s.n;int main(void){return *p;}'),
    valid('nested-member-address', 'struct A{char pad;int n;};struct B{char pad;struct A a;};struct B b={0,{0,42}};int *p=&b.a.n;int main(void){return *p;}'),
    valid('anonymous-member-address', 'struct S{char pad;union{int n;};};struct S s={0,{42}};int *p=&s.n;int main(void){return *p;}'),
    valid('member-array-decay-offset', 'struct S{int a[2];};struct S s={{20,22}};int *p=s.a+1;int main(void){return *p+20;}'),
    valid('literal-member-address', 'struct S{int pad;int n;};int *p=&(struct S){0,42}.n;int main(void){return *p;}'),
    valid('cast-static-address', 'struct S{int n;};struct S s={42};int *p=(int*)(void*)&s;int main(void){return *p;}'),
    valid('indirection-cancels-address', 'int a[2]={20,22};int *p=&*(a+1);int main(void){return *p+20;}'),
    valid('string-address-offset', 'char *p="!x"+1;int main(void){return *p==\'x\' ? 42:1;}'),
    valid('function-address-indirection', 'int f(void){return 42;}int (*p)(void)=&*f;int main(void){return p();}'),
    valid('static-address-ice-offset', 'enum{N=1};int a[2]={20,22};int *p=a+(int)N;int main(void){return *p+20;}'),
    valid('generic-selected-static-address', 'int a[2]={20,22};int *p=_Generic(1,int:a+1,default:(int*)0);int main(void){return *p+20;}'),
    valid('conditional-selected-static-address', 'int a[2]={20,22};int *p=1?a+1:(int*)0;int main(void){return *p+20;}'),
    valid('conditional-unselected-call', 'int f(void){return 1;}int n=1?42:f();int main(void){return n;}', '6.6p3;6.5.15p4'),
    valid('integer-constant-explicit-pointer-cast', 'int *p=(int*)(40+2);int main(void){return p!=(int*)0 ? 42:1;}', '6.6p9;6.3.2.3p5'),
    valid('sizeof-file-array-literal', '_Static_assert(sizeof((int[]){1,2})==2*sizeof(int),"size");int main(void){return 42;}', '6.5.2.5p5;6.5.3.4p2'),
    valid('automatic-goto-identity', 'int main(void){int *p=0,*q=0;int j=0;again:q=p;p=(int[]){j++};if(j<2)goto again;return p==q && *q==1 ? 42:1;}', '6.5.2.5p15,p16'),
    valid('sizeof-automatic-literal-does-not-run', 'int main(void){int n=0;int size=sizeof((int[]){n++});return n==0 && size==sizeof(int) ? 42:1;}', '6.5.3.4p2'),
    valid('local-static-address', 'int main(void){static int a=42;static int *p=&a;return *p;}', '6.6p9;6.7.9p4'),
    valid('local-static-array-offset', 'int main(void){static int a[2]={20,22};static int *p=&a[1];return a[0]+*p;}', '6.6p9;6.7.9p4'),
    valid('local-static-shadow-identities', 'int main(void){static int a=20;static int *p=&a;int sum=*p;{static int a=22;static int *p=&a;sum+=*p;}return sum;}', '6.2.1;6.6p9'),
    valid('local-static-enum-initializer', 'enum{N=20};int main(void){enum{N=42};static int n=N;return n;}', '6.2.1;6.6p6;6.7.9p4'),
    valid('local-static-aggregate-enum-initializer', 'struct S{int n;};int main(void){enum{N=42};static struct S s={N};return s.n;}', '6.2.1;6.6p6;6.7.9p4'),
    valid('local-static-local-tag-layout', 'struct S{int a;};int main(void){struct S{char pad;int n;};static struct S s={0,42};static int *p=&s.n;return *p;}', '6.2.1;6.7.2.3;6.6p9'),
    invalid('block-literal-cannot-initialize-static-pointer', 'int main(void){static int *p=(int[]){42};return *p;}', 'constant expression', '6.5.2.5p5;6.7.9p4'),
    invalid('automatic-address-cannot-initialize-static-pointer', 'int main(void){int a=42;static int *p=&a;return *p;}', 'static storage duration'),
    invalid('stored-pointer-value-is-not-address-constant', 'int a;int *p=&a;int *q=p;int main(void){return 42;}', "stored value"),
    invalid('stored-scalar-value-is-not-constant', 'int a=42;int b=a;int main(void){return b;}', "stored value"),
    invalid('stored-member-value-is-not-constant', 'struct S{int n;};struct S s={42};int b=s.n;int main(void){return b;}', "stored value"),
    invalid('address-offset-cannot-read-object', 'int a[2];int n=1;int *p=a+n;int main(void){return 42;}', "stored value"),
    invalid('file-literal-initializer-cannot-call', 'int f(void){return 42;}int *p=(int[]){f()};int main(void){return *p;}', "constant expression"),
    invalid('sizeof-static-literal-initializer-still-constant', 'int f(void){return 42;}_Static_assert(sizeof((int[]){f()})==sizeof(int),"size");int main(void){return 42;}', "constant expression", '6.5.2.5p6;6.7.9p4'),
    invalid('literal-does-not-see-future-tag-completion', 'struct S;struct S *p=&(struct S){42};struct S{int n;};int main(void){return 42;}', 'incomplete C aggregate', '6.5.2.5p1;6.7.2.3'),
    invalid('const-literal-retains-qualifier', 'int *p=(const int[]){42};int main(void){return *p;}', 'discarded qualifiers', '6.5.16.1p1;6.7.9p11'),
]


def main() -> int:
    argv = list(sys.argv[1:])
    # The generated clause manifest is a normal fingerprinted shared-runner
    # input. It stays inside target so relative input paths remain meaningful.
    directory = ROOT / 'target'
    directory.mkdir(exist_ok=True)
    source_path = Path(__file__).resolve()
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='c11-static-literals-', dir=directory) as generated:
        manifest = Path(generated) / 'cases.json'
        manifest.write_text(json.dumps(dict(format=1, target='windows-x86_64-llp64',
            full_conformance_claimed=False, cases=CASES), indent=2)+'\n', encoding='utf-8')
        if '--reference' not in argv and Path('D:/LLVM/bin/clang.exe').exists():
            argv = ['--reference','D:/LLVM/bin/clang.exe',*argv]
        status = conformance_main(['--probe-manifest',str(manifest),
            '--report',str(ROOT/'target/c11-static-literals.json'),*argv])
    unchanged = before == hashlib.sha256(source_path.read_bytes()).hexdigest()
    if not unchanged:
        print('FAIL static literal corpus source changed during execution', flush=True)
        return 1
    return status


if __name__ == '__main__':
    raise SystemExit(main())
