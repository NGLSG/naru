"""System C11 header baseline. Failures remain failures, not expected passes.

An empty translation unit using a header is only an initial integration gate;
passing it does not establish the header's interfaces or runtime semantics.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from native_process import execute
from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs
import c11_reference_headers

ROOT = Path(__file__).resolve().parents[1]
HEADERS = (
    'assert.h', 'complex.h', 'ctype.h', 'errno.h', 'fenv.h', 'float.h',
    'inttypes.h', 'iso646.h', 'limits.h', 'locale.h', 'math.h', 'setjmp.h',
    'signal.h', 'stdalign.h', 'stdarg.h', 'stdatomic.h', 'stdbool.h',
    'stddef.h', 'stdint.h', 'stdio.h', 'stdlib.h', 'stdnoreturn.h',
    'string.h', 'tgmath.h', 'threads.h', 'time.h', 'uchar.h', 'wchar.h', 'wctype.h',
)

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--header', choices=HEADERS, action='append')
    parser.add_argument('--opt', choices=['0','2'], action='append')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--memory-mib',type=int,default=2048)
    parser.add_argument('--timeout',type=float,default=60)
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-headers.json')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 64: parser.error('--jobs must be 1..64')
    if args.memory_mib < 1 or args.timeout <= 0: parser.error('Resource limits must be positive')
    reference = args.reference or shutil.which('clang.exe')
    if not reference: parser.error('A reference Clang is required')
    compiler = args.compiler.resolve()
    frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    paths = [compiler, compiler.parent/'naru_mlir_backend.dll', Path(__file__),ROOT/'tests/native_process.py',
             ROOT/'tests/c11_reference_headers.py', *c11_rule_inputs()]
    before = {str(p):digest(p) for p in paths}
    headers = list(dict.fromkeys(args.header or HEADERS))
    opts = list(dict.fromkeys(args.opt or ['0','2']))
    environment = dict(os.environ, PATH='')
    # Target discovery, like compilation, must work in process. Record the
    # actual SDK header origins; the independent compiler may use resource
    # wrappers for its own intrinsics.
    rules = [] if args.frozen else ['--rules', str(ROOT/'dialects/c11.stx')]
    policy = c11_reference_headers.discover(compiler, rules, ROOT)
    target = policy.target
    origins = {header: policy.origin(header) for header in headers}
    results = []
    with tempfile.TemporaryDirectory(prefix='naru C11 headers ') as directory:
        work = Path(directory)
        reference_flags, reference_view = [], {}
        if 'tgmath.h' in headers:
            reference_flags, reference_view = c11_reference_headers.reference_view(work, policy)
        def run_header(header: str) -> list[dict]:
            folder = work/header.removesuffix('.h'); folder.mkdir()
            source = '#include <'+header+'>\nint main(void){return 42;}\n'
            path = folder/'main.c'; path.write_text(source,encoding='utf-8')
            oracle_error = None
            try:
                oracle = subprocess.run([str(reference),'-std=c11','-pedantic-errors',*reference_flags,'-O2',
                    '-fuse-ld=lld','-fms-runtime-lib=static',str(path),'-o',str(folder/'reference.exe')],
                    capture_output=True,text=True,timeout=30)
                assert oracle.returncode == 0, oracle.stdout+oracle.stderr
                native = execute([str(folder/'reference.exe')],cwd=folder,timeout=3)
                assert native.returncode == 42 and native.stdout == '',str(native)
            except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                oracle_error = str(error)
            rows = []
            for opt in opts:
                row = {'header':header,'clause':'7.1.2','opt':opt,'passed':False,
                       'reference_validated':oracle_error is None,'origin':origins[header]}
                try:
                    assert oracle_error is None,'Reference: '+str(oracle_error)
                    output = folder/('program-O'+opt+'.exe')
                    output.write_bytes(b'previous-success')
                    built = execute([str(compiler),'build',str(path),*rules,
                        '--frontend','c11.frontend','--entry','c11.item','--unit','program',
                        '--relation','c11.emit_program','--runtime','crt-static',
                        '--rule-depth','1024','--rule-budget','100000000',
                        '--parse-budget','100000000','--opt-level',opt,'--target','exe',
                        '-o',str(output),'--report',str(folder/('build-O'+opt+'.json'))],
                        cwd=folder,env=environment,timeout=args.timeout,memory_limit=args.memory_mib*1024**2)
                    row.update(compile_exit=built.returncode,seconds=built.elapsed_seconds,
                               peak_commit_bytes=built.peak_memory_bytes)
                    if built.returncode != 0:
                        assert output.read_bytes()==b'previous-success','failed build replaced the artifact'
                    assert built.returncode == 0,built.stdout+built.stderr
                    info=json.loads((folder/('build-O'+opt+'.json')).read_text())
                    assert info['backend']=='in-process' and info['processes_spawned']==0,info
                    native=execute([str(output)],cwd=folder,timeout=3)
                    assert native.returncode==42 and native.stdout=='',str(native)
                    row['passed']=True
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    row['error']=str(error)[-4000:]
                rows.append(row)
            return rows
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(run_header,h):h for h in headers}
            for future in as_completed(futures):
                rows=future.result(); results.extend(rows)
                print(('PASS ' if all(r['passed'] for r in rows) else 'FAIL ')+
                      futures[future]+' '+str(sum(r['passed'] for r in rows))+'/'+str(len(rows)),flush=True)
    unchanged = before == {str(p):digest(p) for p in paths} and c11_reference_headers.unchanged(reference_view)
    if args.frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    unchanged = unchanged and all(origin is None or digest(Path(origin['path']))==origin['sha256']
                                  for origin in origins.values())
    results.sort(key=lambda row:(HEADERS.index(row['header']),row['opt']))
    passed=sum(row['passed'] for row in results)
    report={'format':1,'scope':'header build/execute smoke; interfaces and runtime semantics not certified',
            'full_c11_conformance_claimed':False,'all_headers_selected':len(headers)==len(HEADERS),
            'jobs':args.jobs,'memory_mib':args.memory_mib,'timeout_seconds':args.timeout,
            'compiler':str(compiler),'reference':str(reference),
            'target':target,'header_exclusions':policy.exclusions,'reference_header_view':reference_view,
            'inputs_unchanged':unchanged,'sha256':before,'frozen_provenance':frozen,
            'passed':passed,'total':len(results),'results':results}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{passed}/{len(results)} header checks passed; inputs unchanged: {unchanged}')
    return int(not unchanged or passed != len(results))

if __name__=='__main__':
    raise SystemExit(main())
