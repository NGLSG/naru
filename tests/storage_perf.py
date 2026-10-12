"""Compare scalar windows with whole-object images using the same dynamic core.

The baseline changes only storage.reinterpret in a temporary rule snapshot;
both variants use the current C11 layout and compiler/backend binaries.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', type=int, nargs='+', default=[32,128,512])
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--report', type=Path, default=ROOT/'target/storage-perf.json')
    args = parser.parse_args()
    if args.repeat < 1 or any(n < 2 or n > 16384 for n in args.sizes):
        parser.error('positive repeats and array sizes in 2..16384 are required')
    compiler = ROOT/'target/naru.exe'
    paths = [compiler,compiler.parent/'naru_mlir_backend.dll',Path(__file__),*sorted((ROOT/'dialects').rglob('*.stx'))]
    fingerprint = lambda: {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = fingerprint(); results = []
    with tempfile.TemporaryDirectory(prefix='naru storage comparison ') as directory:
        work = Path(directory)
        snapshots = {}
        for variant in ('image','windows'):
            rules = work/variant/'dialects'
            for path in (ROOT/'dialects').rglob('*.stx'):
                out = rules/path.relative_to(ROOT/'dialects'); out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(path.read_bytes())
            if variant == 'image':
                storage = rules/'storage.stx'
                text, count = re.subn(r'effect reinterpret\(\$value,\$source,\$destination\).*?;\n',
                    'effect reinterpret($value,$source,$destination) => unpack(resize(pack($value,$source),width($source),width($destination)),$destination);\n',
                    storage.read_text(),count=1,flags=re.S)
                assert count == 1
                storage.write_text(text)
            snapshots[variant] = rules
        snapshot_hashes = {v:{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(r.rglob('*.stx'))} for v,r in snapshots.items()}
        for count in args.sizes:
            source = work/'main.c'
            source.write_text(f'union U {{int a[{count}];double d;}};int main(void){{int first=20,second=22;union U u={{{{first,second}}}};return u.a[0]+u.a[1];}}\n')
            for repeat in range(args.repeat):
                # Alternate order to avoid always giving one variant a warm host.
                for variant in (('image','windows') if repeat % 2 == 0 else ('windows','image')):
                    output = work/'program.exe'; build_report = work/'build.json'
                    record = dict(elements=count,repeat=repeat,variant=variant,passed=False)
                    try:
                        built = execute([str(compiler),'build',str(source),'--rules',str(snapshots[variant]/'c11.stx'),
                            '--frontend','c11.frontend','--entry','c11.item','--unit','program','--relation','c11.emit_program',
                            '--runtime','crt-static','--target','exe','--opt-level','2','--rule-depth','1024',
                            '--rule-budget','100000000','--parse-budget','100000000','--report',str(build_report),'-o',str(output)],
                            cwd=work,env=dict(os.environ,PATH=''),timeout=60,memory_limit=1536*1024**2)
                        record.update(seconds=built.elapsed_seconds,peak_commit_bytes=built.peak_memory_bytes)
                        assert built.returncode == 0,built.stdout+built.stderr
                        ran = execute([str(output)],cwd=work,timeout=3,memory_limit=64*1024**2)
                        assert ran.returncode == 42,ran
                        info = json.loads(build_report.read_text())
                        assert info['backend']=='in-process' and info['processes_spawned']==0,info
                        record['passed'] = True
                    except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                        record['error'] = str(error)[-2500:]
                    results.append(record)
                    print(json.dumps(record),flush=True)
        assert snapshot_hashes == {v:{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(r.rglob('*.stx'))} for v,r in snapshots.items()}
    summary = []
    for count in args.sizes:
        for variant in ('image','windows'):
            rows = [r for r in results if r['elements']==count and r['variant']==variant and r['passed']]
            summary.append(dict(elements=count,variant=variant,successful_samples=len(rows),
                median_seconds=statistics.median(r['seconds'] for r in rows) if rows else None,
                peak_commit_bytes=max((r['peak_commit_bytes'] for r in rows),default=None)))
    report = dict(passed=all(r['passed'] for r in results) and before==fingerprint(),inputs_unchanged=before==fingerprint(),
        measures='compiler time and memory, not program runtime',sha256=before,rule_snapshots=snapshot_hashes,summary=summary,results=results)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return int(not report['passed'])

if __name__ == '__main__':
    raise SystemExit(main())
