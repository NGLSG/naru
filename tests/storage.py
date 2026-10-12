"""Generic object windows, padding, cursors and malformed target layout facts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--report', type=Path, default=ROOT/'target/storage.json')
    args = parser.parse_args()
    paths = [args.compiler.resolve(), args.compiler.resolve().parent/'naru_mlir_backend.dll',
             ROOT/'dialects/storage.stx', ROOT/'tests/fixtures/storage_tests.stx', Path(__file__)]
    fingerprint = lambda: {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = fingerprint(); results = []
    with tempfile.TemporaryDirectory(prefix='naru storage ') as directory:
        work = Path(directory)
        for case in range(12):
            source = work/'main.nru'; source.write_text(f'storage_test {case}\n')
            for opt in ('0','2'):
                output = work/'program.exe'; output.write_bytes(b'previous-success')
                record = dict(case=case, opt=opt, passed=False)
                try:
                    built = execute([str(args.compiler.resolve()),'build',str(source),
                        '--rules',str(ROOT/'dialects/storage.stx'),'--rules',str(ROOT/'tests/fixtures/storage_tests.stx'),
                        '--opt-level',opt,'--target','exe','-o',str(output)],
                        cwd=work,env=dict(os.environ,PATH=''),timeout=20,memory_limit=512*1024**2)
                    if case < 7:
                        assert built.returncode == 0, built.stdout+built.stderr
                        ran = execute([str(output)],cwd=work,timeout=3,memory_limit=64*1024**2)
                        assert ran.returncode == 42, ran
                    else:
                        expected = 'storage image width exceeds resource limit' if case == 11 else 'storage members must be ordered, nonoverlapping and inside the object'
                        assert built.returncode == 1 and expected in built.stdout+built.stderr,built
                        assert output.read_bytes() == b'previous-success'
                    record['passed'] = True
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    record['error'] = str(error)[-2500:]
                results.append(record)
                print(('PASS ' if record['passed'] else 'FAIL ')+f'{case} O{opt}'+(': '+record['error'] if not record['passed'] else ''),flush=True)
    unchanged = before == fingerprint()
    report = dict(passed=all(r['passed'] for r in results) and unchanged, inputs_unchanged=unchanged,sha256=before,results=results)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    return int(not report['passed'])

if __name__ == '__main__':
    raise SystemExit(main())
