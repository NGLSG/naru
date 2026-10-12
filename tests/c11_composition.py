"""C rule composition: aggregate layout, enum identities, jumps and symbol policy.

Clang validates the source and expected result independently. Every Naru build
runs with an empty PATH, no child processes and bounded time/private commit.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

VALID = {
    'builtin specifier words may be reordered': 'int main(void){long unsigned int n=40;int short unsigned step=1;signed long long int extra=1;double long value=0;return n+step+extra+(int)value;}',

    'all bitwise compound operators compose': 'int main(void){unsigned n=20;n|=2;n^=4;n&=31;n<<=1;n>>=1;return n+24;}',
    'compound shift promotes left before narrowing': 'int main(void){unsigned char n=21;n<<=1;unsigned int count=1;int negative=-84;negative>>=count;return n+negative+42;}',
    'compound assignment evaluates its lvalue once': 'int main(void){int values[2]={20,1};int i=0;values[i++]|=2;values[i++]<<=1;return values[0]+values[1]+i+16;}',
    'system warning pragmas compose inside expressions': '#define ID(x) (__pragma(warning(suppress:6334)) (x))\nint main(void){__pragma(warning(push)) int n=ID(42);__pragma(warning(disable:4000 4001)) __pragma(warning(pop)) return n;}',

    'union alternatives overlap and preserve alignment': '''union U { double alignment; unsigned char bytes[13]; int value; };
        _Static_assert(sizeof(union U)==16,"size"); _Static_assert(_Alignof(union U)==8,"align");
        int main(void){union U u;u.bytes[0]=42;return u.bytes[0];}''',
    'union type punning uses shared bytes': '''union U { unsigned int bits; float value; };
        int main(void){union U u;u.value=1.0f;if(u.bits==0x3f800000u)return 42;return 1;}''',
    'anonymous members use nested layout offsets': '''struct S {char tag; union {double value;struct {int a,b;};};int data[2];};
        _Static_assert(sizeof(struct S)==24,"size");int main(void){struct S s;s.a=20;s.b=22;s.data[1]=0;return s.a+s.b+s.data[1];}''',
    'nested tags are shared through independent declarators': '''struct Outer {struct Inner {int value;} first;};
        struct Inner other;int main(void){struct Outer o;o.first.value=20;other.value=22;return o.first.value+other.value;}''',
    'recursive union pointers keep the tag identity': '''union Node {int value;union Node *next;};
        int main(void){union Node a,b;a.value=42;b.next=&a;return b.next->value;}''',
    'qualified inline tag pointers complete on dereference': '''struct S {int n;};
        int main(void){struct S s;s.n=42;const struct S *p=&s;return p->n;}''',
    'qualified anonymous struct pointers complete nested typedef fields': '''typedef struct Hook {int value;} Hook;
        typedef struct {Hook hook;} Buffer;
        static int read(const Buffer *p){return p->hook.value;}
        int main(void){Buffer b;b.hook.value=42;return read(&b);}''',
    'qualified anonymous union pointers complete nested tag fields': '''struct Pair {int left;int right;};
        typedef union {struct Pair pair;long long storage;} Value;
        static int read(const volatile Value *p){return p->pair.left+p->pair.right;}
        int main(void){Value v;v.pair.left=20;v.pair.right=22;return read(&v);}''',
    'multiple pointer levels complete anonymous records containing tag arrays': '''typedef struct Cell {int value;} Cell;
        typedef struct {Cell cells[2];} Row;
        static int read(Row **rows){return (*rows)->cells[0].value+(*rows)->cells[1].value;}
        int main(void){Row row;row.cells[0].value=20;row.cells[1].value=22;Row *p=&row;return read(&p);}''',
    'flexible array offset is independent of trailing padding': '''#include <stdlib.h>
        struct Packet {double alignment;char tag;unsigned char data[];};
        _Static_assert(sizeof(struct Packet)==16,"size");int main(void){struct Packet *p=malloc(sizeof(struct Packet)+8);
        if(!p)return 1;p->data[0]=42;int result=((unsigned char*)p)[9];free(p);return result;}''',
    'sizeof does not decay a member array or evaluate its index': '''struct S{int data[3];};int main(void){struct S s;int n=0;
        if(sizeof(s.data)==12 && sizeof(s.data[++n])==4 && n==0)return 42;return 1;}''',
    'enumerators compose with array bounds and shadowing': '''enum Mode {First=1,Next,Answer=First+41,};int values[Next];
        _Static_assert(Answer==42,"enum");int main(void){enum Mode n=Answer;{int Answer=1;n=n+Answer-1;}return n;}''',
    'anonymous enum flags are integer constant expressions': '''enum {Bit=1<<4,Mask=Bit|2,All=~0,Yes=!0};
        _Static_assert((0 && 1/0)==0,"short circuit");int main(void){return Mask+Bit+7+Yes;}''',
    'zero initialized enum uses the generic integer policy': '''enum E {Answer=42};enum E value;
        int main(void){enum E local;local=Answer;return local+value;}''',
    'for clauses and comma sequencing compose': '''int main(void){int n=0,v=0;for(;;){if(++n==2)break;continue;}
        for(;v<2;)v++;for(int i=0,j=0;i<2;++i,++j)v+=i+j;return (n=38,n+v);}''',
    'switch evaluates once and permits shared cases and fallthrough': '''enum E {First=1};
        int main(void){int x=0,n=0;switch(++x){default:n=1;break;case First:case 2:n=20;case 3:n+=22;break;}return n+x-1;}''',
    'switch without cases still evaluates its selector': '''int main(void){int n=41;switch(++n){}return n;}''',
    'switch continue belongs to the enclosing for loop': '''int main(void){int n=0;for(int i=0;i<3;++i){switch(i){case 0:continue;
        default:n+=21;break;}}return n;}''',
    'nested switch owns only its own cases and breaks': '''int main(void){int n=0;switch(1){case 1:switch(2){case 2:n=20;break;
        default:n=1;}n+=22;break;default:n=1;}return n;}''',
    'unsigned switch keys retain their converted bit pattern': '''int main(void){unsigned int n=0xffffffffu;
        switch(n){case -1:return 42;default:return 1;}}''',
    'goto preserves forward backward and otherwise unreachable labels': '''int main(void){int n=0;goto start;
        again:n++;if(n<2)goto again;return n+40;start:goto again;}''',
    'goto can enter a scope whose preceding statement returned': '''int main(void){goto result;{return 1;result:return 42;}}''',
    'unreachable suffix labels survive branches that both return': '''int main(void){int n=0;goto result;
        if(n)return 1;else return 2;result:return 42;}''',
    'switch labels can enter a nested loop': '''int main(void){int n=0;switch(0){case 0:do {n+=21;case 1:n+=21;}while(0);}
        return n;}''',
    'DLL attributes compose with noinline and calling convention': '''__declspec(dllexport) __declspec(noinline) int __stdcall answer(void){return 42;}
        __declspec(dllexport) int exported_value=0;int main(void){return answer()+exported_value;}''',
}

INVALID = {
    'duplicate builtin type words': ('int int n;int main(void){return 42;}', 'duplicate C type specifier'),
    'conflicting integer signs': ('signed unsigned int n;int main(void){return 42;}', 'incompatible C type specifiers'),
    'integer and floating words cannot mix': ('double unsigned n;int main(void){return 42;}', 'incompatible C type specifiers'),
    'long long double is not a C11 type': ('long double long n;int main(void){return 42;}', 'incompatible C type specifiers'),

    'compound assignment rejects const lvalues': ('int main(void){const int n=42;n|=1;return n;}', 'assignment to a const C object'),
    'compound shift rejects floating operands': ('int main(void){int n=42;n<<=1.0;return n;}', 'shift requires integer operands'),
    'warning pragma must terminate': ('int main(void){return __pragma(warning(suppress:6334) 42;}', 'unterminated MSVC warning pragma'),

    'tag redefinition': ('struct S{int n;};struct S{int n;};int main(void){return 42;}', 'duplicate or incompatible C tag'),
    'unused anonymous typedef still validates its layout': ('typedef union {int n;int values[];} Invalid;int main(void){return 42;}', 'flexible array must be the final'),
    'different kinds share the tag namespace': ('struct S{int n;};union S{int n;};int main(void){return 42;}', 'duplicate or incompatible C tag'),
    'promoted anonymous member names cannot collide': ('struct S{int n;union{int n;float f;};};int main(void){return 42;}', 'duplicate C aggregate member'),
    'flexible array must be last': ('struct S{int n;int values[];int last;};int main(void){return 42;}', 'flexible array must be the final'),
    'flexible array cannot be a union member': ('union U{int n;int values[];};int main(void){return 42;}', 'flexible array must be the final'),
    'flexible array member has no sizeof': ('struct S{int n;int values[];};int main(void){struct S s;return sizeof(s.values);}', 'sizeof requires a complete C array'),
    'enum constants cannot be assigned': ('enum E{Answer=42};int main(void){Answer=1;return 42;}', 'enumeration constant'),
    'enum constants share the ordinary identifier namespace': ('enum E{Answer=42};int Answer;int main(void){return 42;}', 'conflicts with another identifier'),
    'duplicate enumerators': ('enum E{Answer=42,Answer=1};int main(void){return 42;}', 'duplicate C enumeration constant'),
    'C11 enumerators must fit int': ('enum E{Answer=2147483648};int main(void){return 42;}', 'representable as int'),
    'undefined goto target': ('int main(void){goto missing;return 42;}', 'undefined C label'),
    'duplicate function label': ('int main(void){same:;same:return 42;}', 'duplicate C label'),
    'case requires a switch': ('int main(void){case 1:return 42;}', 'outside a switch'),
    'case keys collide after selector conversion': ('int main(void){unsigned n=0;switch(n){case -1:return 1;case 0xffffffffu:return 42;}}', 'duplicate C switch case after conversion'),
    'default requires uniqueness': ('int main(void){switch(0){default:return 1;default:return 42;}}', 'duplicate C switch default'),
    'switch alone cannot accept continue': ('int main(void){switch(0){default:continue;}return 42;}', 'continue outside a loop'),
    'const promoted union member is not writable': ('union U{const int n;float f;};int main(void){union U u;u.n=42;return u.n;}', 'assignment to a const C object'),
    'dllimport definition is not a declaration': ('__declspec(dllimport) int answer(void){return 42;}int main(void){return answer();}', 'imports must be declarations'),
    'internal DLL export is invalid': ('__declspec(dllexport) static int answer(void){return 42;}int main(void){return answer();}', 'Windows external symbol'),
    'conflicting DLL storage declarations': ('__declspec(dllimport) int answer(void);__declspec(dllexport) int answer(void){return 42;}', 'conflicting C DLL storage'),
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    p.add_argument('--reference', type=Path)
    p.add_argument('--frozen', action='store_true')
    p.add_argument('--report', type=Path, default=ROOT/'target/c11-composition.json')
    a = p.parse_args(); compiler = a.compiler.resolve()
    reference = a.reference or shutil.which('clang.exe')
    if not reference: raise SystemExit('A reference Clang is required for this test suite.')
    results = []
    with tempfile.TemporaryDirectory(prefix='naru C composition ') as directory:
        work = Path(directory)
        common = ([] if a.frozen else ['--rules',str(ROOT/'dialects/c11.stx')])+[
            '--frontend','c11.frontend','--entry','c11.item','--relation','c11.emit_program','--unit','program',
            '--runtime','crt-static','--rule-budget','100000000','--parse-budget','100000000']
        for name, source in {**VALID, **{k:v[0] for k,v in INVALID.items()}}.items():
            levels = ('0','2') if name in VALID else ('2',)
            oracle_error = None
            path = work/'main.c';path.write_text(source)
            if name in VALID:
                try:
                    r = subprocess.run([str(reference),'-std=c11','-O2','-fuse-ld=lld','-fms-runtime-lib=static',str(path),'-o',str(work/'reference.exe')],
                        capture_output=True,text=True,timeout=60)
                    assert r.returncode==0,r.stdout+r.stderr
                    assert execute([str(work/'reference.exe')],cwd=work,timeout=10).returncode==42
                except (AssertionError,OSError,subprocess.TimeoutExpired) as e: oracle_error=str(e)
            for level in levels:
                item = {'name':name,'opt_level':level,'passed':False}
                try:
                    assert oracle_error is None,'reference: '+str(oracle_error)
                    output=work/'program.exe';output.write_bytes(b'previous-success')
                    report=work/'build.json'
                    r=execute([str(compiler),'build',str(path),*common,'--opt-level',level,'--target','exe','-o',str(output),'--report',str(report)],
                        cwd=work,env=dict(os.environ,PATH=''),timeout=60,memory_limit=2*1024**3)
                    if name in INVALID:
                        assert r.returncode==1 and INVALID[name][1] in r.stdout+r.stderr,r.stdout+r.stderr
                        assert output.read_bytes()==b'previous-success','failed build replaced the artifact'
                    else:
                        assert r.returncode==0,r.stdout+r.stderr
                        assert execute([str(output)],cwd=work,timeout=10).returncode==42,'native result differs from reference'
                        info=json.loads(report.read_text())
                        assert info['backend']=='in-process' and info['processes_spawned']==0,info
                    item.update(passed=True,seconds=r.elapsed_seconds,peak_commit_bytes=r.peak_memory_bytes)
                except (AssertionError,OSError,subprocess.TimeoutExpired) as e: item['error']=str(e)
                results.append(item)
                print(('PASS ' if item['passed'] else 'FAIL ')+name+' O'+level+('' if item['passed'] else ': '+item['error']),flush=True)
    passed=sum(r['passed'] for r in results)
    a.report.write_text(json.dumps({'passed':passed,'total':len(results),'reference':str(reference),'results':results},indent=2)+'\n')
    print(f'{passed}/{len(results)} C composition checks passed')
    return int(passed!=len(results))

if __name__=='__main__':raise SystemExit(main())
