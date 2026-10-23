"""Compile coroutine providers and consumers as independent object modules."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import tempfile
import coro
from native_process import execute
from frozen_snapshot import validate_frozen

ROOT = Path(__file__).resolve().parents[1]
CONSUMERS = {
    'task': 'extern "C" {fn answer()->task<i32>;}fn main()->i32{let t=answer();let n=await t;destroy(t);return n;}',
    'generator': 'extern "C" {fn legacy()->generator<i32>;}fn main()->i32{let g=legacy();resume(g);let n=current(g);destroy(g);return n;}',
    'async generator': 'extern "C" {fn counter()->async_generator<i32>;}fn main()->i32{let g=counter();await next(g);let n=current(g);destroy(g);return n;}',
}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen',action='store_true')
    parser.add_argument('--report',type=Path,default=ROOT/'target/coro-abi.json')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    provenance = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/coro.stx']) if args.frozen else None
    paths = [Path(__file__),compiler,compiler.parent/'naru_mlir_backend.dll',ROOT/'target/naru_tasks.lib',ROOT/'target/naru_coro_plugin.dll',*sorted((ROOT/'dialects').rglob('*.stx'))]
    fingerprint = lambda: {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = fingerprint()
    environment = dict(os.environ,PATH='')
    rules = [] if args.frozen else ['--rules',str(ROOT/'dialects/coro.stx')]
    common = [*rules,'--unit','program','--relation','coro.emit_program','--runtime','crt-static','--lowering-pipeline',coro.PIPELINE,'--pass-plugin',str(ROOT/'target/naru_coro_plugin.dll')]
    rows = []
    with tempfile.TemporaryDirectory(prefix='naru independent coro modules ') as directory:
        work = Path(directory)
        provider = work/'provider.nru'
        provider.write_text('async fn answer()->i32{return 42;}async coro fn counter()->i32{yield 42;}coro fn legacy()->i32{yield 42;}')
        for level in ('0','2'):
            obj = work/f'provider-O{level}.obj'
            built = execute([str(compiler),'build',str(provider),*common,'--target','object','--opt-level',level,'-o',str(obj)],cwd=work,env=environment,timeout=30)
            assert built.returncode == 0,built.stdout+built.stderr
            for name,text in CONSUMERS.items():
                row = {'name':name,'opt':level,'passed':False}
                try:
                    source = work/'consumer.nru'; source.write_text(text)
                    output = work/'consumer.exe'; report = work/'build.json'
                    built = execute([str(compiler),'build',str(source),*common,'--target','exe','--opt-level',level,'--link-object',str(obj),'--link-library',str(ROOT/'target/naru_tasks.lib'),'--report',str(report),'-o',str(output)],cwd=work,env=environment,timeout=30)
                    assert built.returncode == 0,built.stdout+built.stderr
                    details = json.loads(report.read_text())
                    assert details['processes_spawned'] == 0
                    actual = execute([str(output)],cwd=work,env=environment,timeout=5)
                    assert actual.returncode == 42,(actual.returncode,actual.stdout,actual.stderr)
                    row.update(passed=True,exit_code=actual.returncode,processes_spawned=0)
                except (AssertionError,OSError) as error:
                    row['error'] = str(error)
                rows.append(row)
                print(('PASS ' if row['passed'] else 'FAIL ')+name+' O'+level,flush=True)
    unchanged = before == fingerprint()
    passed = sum(row['passed'] for row in rows)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'passed':passed,'total':len(rows),'inputs_unchanged':unchanged,'frozen_provenance':provenance,'sha256':before,'results':rows},indent=2)+'\n')
    print(f'{passed}/{len(rows)} independent module checks; inputs unchanged: {unchanged}')
    return int(not unchanged or passed != len(rows))

if __name__ == '__main__': raise SystemExit(main())
