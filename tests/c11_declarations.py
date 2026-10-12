"""Native declaration composition and persistent static-object regression."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from native_process import execute

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',type=Path,default=ROOT/'target/naru.exe')
    a=p.parse_args(); compiler=a.compiler.resolve(); results=[]
    valid={
        'qualified tagged pointer increment and subtraction retain record stride': 'struct Row{int x;int padding;};int main(void){struct Row a[3]={{20,0},{22,0},{0,0}};const struct Row *p=a;p++;p+=1;if(p-a==2)return a[0].x+a[1].x;return 1;}',
        'const flexible array member decays with element qualifiers': '#include <stdlib.h>\nstruct Packet{int n;int a[];};int read(const struct Packet *p){return p->a[0];}int main(void){struct Packet *p=malloc(sizeof(*p)+sizeof(int));if(!p)return 1;p->a[0]=42;int n=read(p);free(p);return n;}',
        'unsized local and global arrays infer designated maximum bound': 'enum {last=4};static const int values[]={[last]=40,[1]=2};int main(void){int a[]={1,2,3};if(sizeof(values)==5*sizeof(int) && sizeof(a)==3*sizeof(int))return values[4]+values[1];return 1;}',
        'unsized compound literal decays into a function argument': 'int sum(const int *a,int n){int result=0;for(int i=0;i<n;++i)result+=a[i];return result;}int main(void){return sum((const int[]){20,22},2);}',
        'static tables compose strings function addresses and null constants': 'int answer(void){return 42;}typedef struct {const char *name;int(*call)(void);void *context;}Entry;static const Entry entries[]={{"answer",answer,0},{0,0,0}};int main(void){if(entries[0].name[0]==\'a\' && entries[1].name==0)return entries[0].call();return 1;}',
        'comma declarators keep each pointer binding': 'int *p, value=42; int main(void){int a=20,*q=&a,b=22; return *q+b;}',
        'typedef groups compose independently': 'typedef int Value,*Pointer; int main(void){Value a=42; Pointer p=&a; return *p;}',
        'nested function pointer and array parameter': 'int add(int a,int b){return a+b;} int apply(int (*f)(int x,int y),int a[2]){return f(a[0],a[1]);} int main(void){int values[2]={20,22};return apply(add,values);}',
        'function returning a function pointer': 'int add(int a,int b){return a+b;} int (*factory(void))(int,int){return add;} int main(void){return factory()(20,22);}',
        'dereferenced function designator': 'int add(int a,int b){return a+b;} int main(void){int (*f)(int,int)=add; return (*f)(20,22);}',
        'static local persists across calls': 'static int next(void){static int value=40;value++;return value;} int main(void){next();return next();}',
        'pointer to array has distinct binding': 'int main(void){int a[3]={0,42,0};int (*p)[3]=&a;return (*p)[1];}',
        'SDK style void pointer parameter': 'typedef unsigned __int64 size_t; void const* __cdecl identity(void const* p, size_t n){return p;} int main(void){int v=42;return *(int*)identity(&v,1);}',
        'generic control and unselected arms are unevaluated': 'int main(void){int x=0;int v=_Generic(++x,int:42,default:++x);return x+v;}',
        'generic default is selected': 'int main(void){return _Generic(2.0,int:1,default:42);}',
        'deprecated annotations compose with declaration groups': '__declspec(deprecated("old")) int value=42,other=0; int main(void){return value;}',
        'nested function annotations compose': '__declspec(noalias) __declspec(deprecated("old")) static int answer(void){return 42;} int main(void){return answer();}',
        'for loop accepts a single statement body': 'int main(void){int result=0;for(int i=0;i<3;++i) result+=14;return result;}',
        'pointer cast preserves the arithmetic source stride': 'int main(void){int a[2]={0,42};return *(int*)(((char*)a+8)-4);}',
        'pointer equality accepts integer and void null constants': 'int main(void){int value=42;int *p=&value;if(p!=(void*)0 && 0!=p && p==&value)return *p;return 1;}',
        'SDK integer suffixes retain exact unsigned 64 bit values': '#include <limits.h>\n_Static_assert(ULLONG_MAX==0xffffffffffffffffUi64,"unsigned maximum");_Static_assert(LLONG_MAX==9223372036854775807I64,"signed maximum");int main(void){unsigned long long n=42i64U;if(n==42 && 0xdeadbeefU==3735928559U && 0x57CEF7==5754615)return 42;return 1;}',
        'varargs traverse register and stack arguments': '#include <stdarg.h>\nstatic int sum(int count,...){va_list ap;va_start(ap,count);int n=0;for(int i=0;i<count;++i)n+=va_arg(ap,int);va_end(ap);return n;}int main(void){return sum(7,1,2,3,4,5,6,21);}',
        'varargs default promotions and copies preserve independent cursors': '#include <stdarg.h>\nstatic int sum(int marker,...){va_list a,b;va_start(a,marker);va_copy(b,a);double n=va_arg(a,double);int v=va_arg(a,int);double same=va_arg(b,double);va_end(a);va_end(b);return (int)(n+same)+v;}int main(void){float v=10;char n=22;return sum(0,v,n);}',
        'varargs function pointer has the same ABI as a direct call': '#include <stdarg.h>\nint answer(int marker,...){va_list a;va_start(a,marker);int n=va_arg(a,int);va_end(a);return n;}int main(void){int(*f)(int,...)=answer;return f(0,42);}',
        'large translation unit uses iterative passes': ''.join(f'int global_{i}={42 if i==1499 else 0};\n' for i in range(1500))+'int main(void){return global_1499;}',
    }
    invalid={
        'typedef initializer is invalid': ('typedef int Value=42;', 'typedef cannot have an initializer'),
        'conflicting typedef types are invalid': ('typedef int Value; typedef long Value;', 'incompatible C typedef'),
        'incompatible function pointer is invalid': ('int add(int a,int b){return a+b;} int main(void){int (*f)(int)=add;return 42;}', 'incompatible C pointer conversion'),
        'generic duplicate associations are invalid': ('int main(void){return _Generic(1,int:42,int:2);}', 'duplicate compatible C generic association'),
        'generic unselected arm still requires valid names': ('int main(void){return _Generic(1,int:42,default:unknown);}', 'unbound environment key'),
        'duplicate locals remain invalid in groups': ('int main(void){int a=20,a=22;return a;}', 'duplicate C local declaration'),
        'function annotation rejects object declarations': ('__declspec(allocator) int value=42; int main(void){return value;}', 'MSVC function annotation requires a function declaration'),
        'va_start requires a variadic enclosing function': ('#include <stdarg.h>\nint main(void){va_list a;int n=0;va_start(a,n);return 42;}', 'va_start requires a variadic function'),
        'va_start requires the final fixed parameter': ('#include <stdarg.h>\nint f(int first,int last,...){va_list a;va_start(a,first);return 42;}int main(void){return f(0,0);}', 'va_start requires the last named parameter'),
    }
    with tempfile.TemporaryDirectory(prefix='naru declarators ') as directory:
        work=Path(directory)
        common=['--rules',str(ROOT/'dialects/c11.stx'),'--frontend','c11.frontend','--entry','c11.item',
            '--relation','c11.emit_program','--unit','program','--runtime','crt-static','--opt-level','2',
            '--rule-budget','100000000','--parse-budget','100000000']
        for name,source in {**valid,**{k:v[0] for k,v in invalid.items()}}.items():
            record={'name':name,'passed':False}
            try:
                path=work/'main.c';path.write_text(source)
                r=execute([str(compiler),'build',str(path),*common,'--target','exe','-o',str(work/'program.exe')],
                    cwd=work,env=dict(os.environ,PATH=''),timeout=60,memory_limit=2*1024**3)
                if name in invalid:
                    assert r.returncode==1 and invalid[name][1] in r.stdout+r.stderr, r.stdout+r.stderr
                else:
                    assert r.returncode==0, f'exit {r.returncode}: '+r.stdout+r.stderr
                    native=execute([str(work/'program.exe')],cwd=work,timeout=10)
                    assert native.returncode==42, str(native)
                record.update(passed=True,seconds=r.elapsed_seconds,peak_commit_bytes=r.peak_memory_bytes)
            except (AssertionError,OSError) as error:
                record['error']=str(error)
            results.append(record)
            print(('PASS ' if record['passed'] else 'FAIL ')+name+('' if record['passed'] else ': '+record['error']),flush=True)
        name='MSVC inline COMDAT shares static storage across translation units'
        record={'name':name,'passed':False}
        try:
            (work/'shared.h').write_text('__inline int next(void){static int n=40;return ++n;}\n')
            (work/'helper.c').write_text('#include "shared.h"\nint first(void){return next();}\n')
            (work/'main.c').write_text('#include "shared.h"\nint first(void);int main(void){if(first()!=41)return 1;return next();}\n')
            samples=[]
            for source,target,output,links in [('helper.c','object','helper.obj',[]),
                    ('main.c','exe','program.exe',['--link-object',str(work/'helper.obj')])]:
                built=execute([str(compiler),'build',str(work/source),*common,'--target',target,'-o',str(work/output),*links],
                    cwd=work,env=dict(os.environ,PATH=''),timeout=60,memory_limit=2*1024**3)
                assert built.returncode==0,built.stdout+built.stderr
                samples.append(built)
            native=execute([str(work/'program.exe')],cwd=work,timeout=10)
            assert native.returncode==42,str(native)
            record.update(passed=True,seconds=sum(s.elapsed_seconds for s in samples),peak_commit_bytes=max(s.peak_memory_bytes for s in samples))
        except (AssertionError,OSError) as error:
            record['error']=str(error)
        results.append(record)
        print(('PASS ' if record['passed'] else 'FAIL ')+name+('' if record['passed'] else ': '+record['error']),flush=True)
    passed=sum(r['passed'] for r in results)
    (ROOT/'target/c11-declarations.json').write_text(json.dumps({'passed':passed,'total':len(results),'results':results},indent=2)+'\n')
    print(f'{passed}/{len(results)} declaration checks passed')
    return int(passed!=len(results))

if __name__=='__main__':raise SystemExit(main())
