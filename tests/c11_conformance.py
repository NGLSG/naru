"""Clause-tagged C11 acceptance cases. Passing this corpus is not certification."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'tests/c11/conformance.json'

def fingerprints(compiler: Path) -> dict[str, str]:
    paths = [MANIFEST, Path(__file__).resolve(), ROOT/'target/naru_mlir_backend.dll',
             *sorted((ROOT/'dialects').rglob('*.stx'))]
    result = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result['compiler:'+str(compiler)] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    backend = compiler.parent/'naru_mlir_backend.dll'
    if backend.is_file(): result['backend:'+str(backend)] = hashlib.sha256(backend.read_bytes()).hexdigest()
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--feature', action='append')
    parser.add_argument('--case', action='append')
    parser.add_argument('--opt', action='append', choices=['0','2'])
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-conformance.json')
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    known_features = {f['id'] for f in manifest['features']}
    known_cases = {c['id'] for c in manifest['cases']}
    if args.feature and set(args.feature)-known_features: parser.error('Unknown feature')
    if args.case and set(args.case)-known_cases: parser.error('Unknown case')
    cases = [c for c in manifest['cases'] if (not args.feature or c['feature'] in args.feature)
             and (not args.case or c['id'] in args.case)]
    if not cases: parser.error('Selected feature has no acceptance cases yet')
    reference = args.reference or shutil.which('clang.exe')
    if not reference: parser.error('A reference Clang is required')
    compiler = args.compiler.resolve()
    before = fingerprints(compiler)
    results = []
    with tempfile.TemporaryDirectory(prefix='naru C11 conformance ') as directory:
        work = Path(directory)
        common = ([] if args.frozen else ['--rules',str(ROOT/'dialects/c11.stx')])+[
            '--frontend','c11.frontend','--entry','c11.item','--unit','program',
            '--relation','c11.emit_program','--runtime','crt-static',
            '--rule-depth','1024','--rule-budget','100000000','--parse-budget','100000000']
        for case in cases:
            path = work/'main.c'
            path.write_text(case['source']+'\n', encoding='utf-8')
            oracle_error = None
            try:
                if 'reject' in case:
                    ref = subprocess.run([str(reference),'-std=c11','-pedantic-errors','-fsyntax-only',str(path)],
                                         capture_output=True,text=True,timeout=20)
                    if case.get('reference_reject_required',True):
                        assert ref.returncode != 0, 'Clang accepted the invalid fixture'
                else:
                    ref = subprocess.run([str(reference),'-std=c11','-pedantic-errors','-O2',
                        '-fuse-ld=lld','-fms-runtime-lib=static',str(path),'-o',str(work/'reference.exe')],
                        capture_output=True,text=True,timeout=20)
                    assert ref.returncode == 0, ref.stdout+ref.stderr
                    native = execute([str(work/'reference.exe')],cwd=work,timeout=3)
                    assert (native.returncode,native.stdout)==(case.get('exit',42),case.get('stdout','')),str(native)
            except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                oracle_error = str(error)
            for opt in args.opt or ['0','2']:
                record = {'id':case['id'],'feature':case['feature'],'clause':case['clause'],
                          'opt':opt,'passed':False}
                output = work/'program.exe'
                output.write_bytes(b'previous-success')
                try:
                    assert oracle_error is None, 'Reference: '+str(oracle_error)
                    built = execute([str(compiler),'build',str(path),*common,'--opt-level',opt,
                        '--target','exe','-o',str(output),'--report',str(work/'build.json')],
                        cwd=work,env=dict(os.environ,PATH=''),timeout=30,memory_limit=512*1024**2)
                    record.update(compile_exit=built.returncode,seconds=built.elapsed_seconds,
                                  peak_commit_bytes=built.peak_memory_bytes)
                    if 'reject' in case:
                        assert built.returncode == 1, built.stdout+built.stderr
                        assert case['reject'] in built.stdout+built.stderr, built.stdout+built.stderr
                        assert output.read_bytes() == b'previous-success','failed build replaced the artifact'
                    else:
                        assert built.returncode == 0, built.stdout+built.stderr
                        native = execute([str(output)],cwd=work,timeout=3,memory_limit=64*1024**2)
                        assert (native.returncode,native.stdout)==(case.get('exit',42),case.get('stdout','')),str(native)
                        info=json.loads((work/'build.json').read_text())
                        assert info['backend']=='in-process' and info['processes_spawned']==0,info
                    record['passed']=True
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    record['error']=str(error)[-4000:]
                results.append(record)
                print(('PASS ' if record['passed'] else 'FAIL ')+case['id']+' O'+opt+
                      (': '+record['error'][-700:] if not record['passed'] else ''),flush=True)
    unchanged = before == fingerprints(compiler)
    passed = sum(r['passed'] for r in results)
    report = {'format':1,'standard':manifest['standard'],'target':manifest['target'],
              'full_c11_conformance_claimed':False,
              'all_configured_cases_selected':len(cases)==len(manifest['cases']),
              'features_without_cases':sorted(known_features-{c['feature'] for c in manifest['cases']}),
              'inputs_unchanged':unchanged,'sha256':before,'passed':passed,'total':len(results),'results':results}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{passed}/{len(results)} clause-tagged checks passed; inputs unchanged: {unchanged}')
    return int(not unchanged or passed != len(results))

if __name__ == '__main__':
    raise SystemExit(main())
