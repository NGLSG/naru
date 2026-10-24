"""Allocation facts compose across libraries and preserve source-site identity."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from native_process import execute
from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs

ROOT=Path(__file__).resolve().parents[1]

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen',action='store_true')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    compiler=args.compiler.resolve()
    fixture=ROOT/'tests/fixtures/allocation_contract.stx'
    frozen=validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    paths=[compiler,compiler.parent/'naru_mlir_backend.dll',Path(__file__),fixture,*c11_rule_inputs()]
    before={str(p):digest(p) for p in paths}
    rules=([] if args.frozen else ['--rules',str(ROOT/'dialects/c11.stx'),'--rules',str(ROOT/'dialects/allocation.stx')])+['--rules',str(fixture)]
    limits=['--rule-depth','1024','--rule-budget','100000000','--parse-budget','100000000']
    environment=dict(os.environ,PATH='')
    results=[]
    def record(name: str, callback) -> None:
        row={'name':name,'passed':False}
        try:
            callback(row)
            row['passed']=True
        except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
            row['error']=str(error)[:4000]
        results.append(row)
        print(('PASS ' if row['passed'] else 'FAIL ')+name+('' if row['passed'] else ': '+row['error']),flush=True)
    with tempfile.TemporaryDirectory(prefix='naru allocation contracts ') as directory:
        work=Path(directory)
        for name,expression,expected,code in [
            ('committed syntax symbol survives rechecking','allocation_contract.syntax_site("int main(void){return *((int[]){42});}")','[12,1,1]',0),
            ('unknown language sites and nested frame boundary','allocation_contract.composed_sites()','[1,1]',0),
            ('type descriptors introduce no runtime allocation','allocation_contract.prune_type_description()','1',0),
            ('conflicting allocator facts fail','allocation_contract.conflicting_sites()','conflicting allocation facts',1),
            ('conflicting allocation arguments fail','allocation_contract.conflicting_arguments()','conflicting allocation facts',1),
        ]:
            def evaluate(row, expression=expression, expected=expected, code=code):
                run=execute([str(compiler),'eval',*rules,'--expr',expression,*limits],cwd=work,env=environment,timeout=30,memory_limit=512*1024**2)
                assert run.returncode==code,run.stdout+run.stderr
                assert (run.stdout.strip().replace(' ','')==expected if code==0 else expected in run.stdout+run.stderr),run.stdout+run.stderr
                row.update(seconds=run.elapsed_seconds,peak_commit_bytes=run.peak_memory_bytes)
            record(name,evaluate)
        cases=[
            ('loop literal occupies one entry slot','int main(void){int i=0;while(i<20000){int*p=(int[64]){i};if(*p!=i)return 1;i++;}return 42;}','!llvm.array<64 x i32>',1),
            ('for step and continue share one entry slot','int main(void){int i=0;int total=0;for(i=0;i<3;i=*((int[]){i+1})){if(i==0)continue;total+=i;}return i==3 && total==3?42:1;}','!llvm.array<1 x i32>',1),
            ('sizeof operand contributes no literal allocation','int main(void){int i=0;int n=sizeof((int[]){i++});return i==0 && n==sizeof(int)?42:1;}','!llvm.array<1 x i32>',0),
            ('unselected generic contributes no literal allocation','int main(void){int i=0;int r=_Generic(0,int:42,default:*((int[]){++i}));return r==42 && i==0?42:1;}','!llvm.array<1 x i32>',0),
            ('generic array control contributes no literal allocation','int main(void){int i=0;int r=_Generic((int[]){i++},int*:42,default:1);return r==42 && i==0?42:1;}','!llvm.array<1 x i32>',0),
        ]
        for index,(name,source,marker,count) in enumerate(cases):
            def inspect_ir(row,index=index,source=source,marker=marker,count=count):
                path=work/f'case-{index}.c';path.write_text(source+'\n',encoding='utf-8')
                output=work/f'case-{index}.mlir'
                run=execute([str(compiler),'build',str(path),*rules,'--frontend','c11.frontend','--entry','c11.item','--unit','program','--relation','c11.emit_program','--runtime','crt-static',*limits,'--opt-level','0','--target','mlir','-o',str(output)],cwd=work,env=environment,timeout=30,memory_limit=512*1024**2)
                assert run.returncode==0,run.stdout+run.stderr
                text=output.read_text(encoding='utf-8')
                allocations=[line for line in text.splitlines() if 'llvm.alloca' in line and marker in line]
                assert len(allocations)==count,allocations
                if count:
                    assert 'cf.br' in text and all(text.index(line)<text.index('cf.br') for line in allocations),text
                row.update(allocation_lines=allocations,seconds=run.elapsed_seconds)
            record(name,inspect_ir)
    unchanged=before=={str(p):digest(p) for p in paths}
    if args.frozen: unchanged=unchanged and frozen==validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    passed=sum(r['passed'] for r in results)
    report=args.report or ROOT/'target'/('allocation-frozen.json' if args.frozen else 'allocation.json')
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps({'passed':passed,'total':len(results),'inputs_unchanged':unchanged,'frozen_provenance':frozen,'sha256':before,'results':results},indent=2)+'\n',encoding='utf-8')
    print(f'{passed}/{len(results)} allocation checks passed; inputs unchanged: {unchanged}')
    return int(passed!=len(results) or not unchanged)

if __name__=='__main__':raise SystemExit(main())
