"""Isolate Vyx SDK regressions from Naru/STX without changing the SDK.

This is an explicit host diagnostic, not a C11 conformance result. A failed
probe stays failed when its behavior differs from the source program.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SDK = Path('E:/Dev/C++/VyxLan-selfhost-yolo/dist/vyx-sdk-windows-x86_64-llvm22')

CONTAINERS = '''module host_probe;
use std.collections;
use std.string;
struct Cell { public value:i64; }
extern "C" { fn host_read(cell:rawptr)->i64; }
fn keys(values:&mut Dict<string,string>)->i64 {
    let names=values.keys();
    return str_char_at(names.get(0),0) as i64;
}
fn main()->i32 {
    let mode=getArg(1);
    if(mode=="builder") {
        var builder=StringBuilder.create();builder.appendI64(4429);
        let text=builder.build();print(text.as_str());return 0;
    }
    if(mode=="keys") {
        var values=Dict::<string,string>.new();
        values.put(str_dup("language.entry"),str_dup("item"));
        print(keys(&mut values));print(keys(&mut values));return 0;
    }
    let count=str_to_int(mode) as i64;
    var cells=Vec::<Cell>.new();var i:i64=0;
    while(i<2048){cells.push(Cell{value:7});i=i+1;}
    var sum:i64=0;i=0;
    while(i<count){let cell=cells.get_ref(i%2048);sum=sum+cell.value+host_read(to_rawptr(cell));i=i+1;}
    print(sum);return 0;
}
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, default=Path(os.environ.get('VYX_SDK_ROOT', str(DEFAULT_SDK))))
    parser.add_argument('--report', type=Path, default=ROOT/'target/vyx-dist-compat.json')
    args = parser.parse_args()
    sdk = args.sdk.resolve()
    compiler = sdk/'bin/vyxc.exe'
    if not compiler.is_file():
        parser.error('Vyx SDK compiler missing: '+str(compiler))
    work = ROOT/'target/vyx-dist-probes'
    work.mkdir(parents=True, exist_ok=True)
    sdk_inputs = [compiler, sdk/'lib/vyx_runtime.lib',
        *sorted((sdk/'std_packages/core').rglob('*.vyx')),
        *sorted((sdk/'std_packages/collections').rglob('*.vyx'))]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in sdk_inputs}
    results = []
    for functions in [2048, 2049]:
        source = work/f'symbols-{functions}.vyx'
        source.write_text('module host_probe;\nfn main()->i32{return last();}\n'+
            ''.join(f'fn sample_{i}()->i32{{return {i%42};}}\n' for i in range(functions-2))+
            'fn last()->i32{return 42;}\n')
        for opt in ['0', '2']:
            start = time.perf_counter()
            run = subprocess.run([str(compiler),'--src=file',str(source),'--emit=hir',
                '--no-implicit-std','-O'+opt], cwd=work, capture_output=True, text=True, timeout=30)
            log = work/f'symbols-{functions}-O{opt}.log'
            log.write_text(run.stdout+run.stderr)
            row = dict(name=f'named module resolves {functions} functions', opt=opt,
                       passed=run.returncode==0, exit=run.returncode,
                       seconds=time.perf_counter()-start, log=str(log))
            results.append(row)
            print(('PASS ' if row['passed'] else 'FAIL ')+row['name']+' O'+opt, flush=True)
    package = work/'containers'
    package.mkdir(exist_ok=True)
    (package/'Vyx.toml').write_text('''[package]
name="naru-host-container-probe"
version="0.1.0"
entry="main.vyx"
[build]
output_dir="target"
cache_dir=".cache"
threads=1
[dependencies]
core={path="std:core",target="std_core"}
collections={path="std:collections",target="std_collections"}
[target.probe]
type="executable"
entry="main.vyx"
auto_sources=false
sources=["main.vyx","escape.c"]
''')
    (package/'main.vyx').write_text(CONTAINERS)
    (package/'escape.c').write_text('#include <stdint.h>\nint64_t host_read(const void *p){return *(volatile const int64_t*)p;}\n')
    for opt in ['0', '2']:
        log = package/f'build-O{opt}.log'
        with log.open('w') as output:
            built = subprocess.run([str(compiler),'build','--target','probe','-j1','-O'+opt],
                                   cwd=package, stdout=output, stderr=subprocess.STDOUT, timeout=180)
        results.append(dict(name='host container probe builds',opt=opt,passed=built.returncode==0,
                            exit=built.returncode,log=str(log)))
        if built.returncode:
            print('FAIL host container build O'+opt, flush=True)
            continue
        for mode, expected in [('builder','4429\n'),('keys','108\n108\n'),
                               ('1000','14000\n'),('1000000','14000000\n')]:
            run = execute([str(package/'target/probe.exe'),mode],cwd=package,
                          env=dict(os.environ,PATH=''),timeout=30,memory_limit=256*1024**2)
            row = dict(name=mode,opt=opt,passed=run.returncode==0 and run.stdout==expected,
                       exit=run.returncode,stdout=run.stdout,stderr=run.stderr,
                       seconds=run.elapsed_seconds,peak_commit_bytes=run.peak_memory_bytes)
            results.append(row)
            print(('PASS ' if row['passed'] else 'FAIL ')+mode+' O'+opt,flush=True)
    unchanged = all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==value for path,value in before.items())
    memory = []
    for opt in ['0', '2']:
        samples = {row['name']: row for row in results if row.get('opt')==opt
                   and row['name'] in ('1000','1000000') and row.get('passed')}
        if len(samples)==2:
            small = samples['1000']['peak_commit_bytes']
            large = samples['1000000']['peak_commit_bytes']
            memory.append(dict(opt=opt,small_iterations=1000,large_iterations=1000000,
                               small_peak_commit_bytes=small,large_peak_commit_bytes=large,
                               growth_bytes=large-small))
            print(f'BORROW MEMORY O{opt}: {small} -> {large} bytes (functional checks do not certify bounded memory)',flush=True)
    report = dict(scope='Vyx host functional diagnostics; memory observations are separate; not C11 acceptance',sdk=str(sdk),
                  fingerprints=before,inputs_unchanged=unchanged,
                  passed=sum(row['passed'] for row in results),total=len(results),
                  borrow_memory_observations=memory,results=results)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"{report['passed']}/{report['total']} host diagnostics passed; inputs unchanged: {unchanged}")
    return int(not unchanged or report['passed']!=report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
