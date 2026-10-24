"""C11 generic selection and source value categories against strict Clang."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from c11_conformance import main as conformance_main, fingerprints
from frozen_snapshot import validate_frozen
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT/'tests/c11/generic.json'


def main() -> int:
    argv = sys.argv[1:]
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    options.add_argument('--report', type=Path, default=ROOT/'target/c11-generic.json')
    options.add_argument('--frozen', action='store_true')
    options.add_argument('--case', action='append')
    options.add_argument('--opt', action='append', choices=['0','2'])
    settings, _ = options.parse_known_args(argv)
    source_path = Path(__file__).resolve()
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    compiler = settings.compiler.resolve()
    before = fingerprints(compiler, MANIFEST)
    status = conformance_main(['--probe-manifest', str(MANIFEST), '--report', str(settings.report), *argv])
    report = json.loads(settings.report.read_text(encoding='utf-8'))
    frozen = validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/c11.stx']) if settings.frozen else None
    cases = json.loads(MANIFEST.read_text(encoding='utf-8'))['cases']
    with tempfile.TemporaryDirectory(prefix='naru C11 generic IR ') as directory:
        work = Path(directory)
        common = ([] if settings.frozen else ['--rules',str(ROOT/'dialects/c11.stx')])+[
            '--frontend','c11.frontend','--entry','c11.item','--unit','program',
            '--relation','c11.emit_program','--rule-depth','1024',
            '--rule-budget','100000000','--parse-budget','100000000']
        for case in cases:
            if 'volatile_loads' not in case or (settings.case and case['id'] not in settings.case):
                continue
            for opt in settings.opt or ['0','2']:
                row = dict(id=case['id']+'-IR', clause=case['clause'], opt=opt, passed=False)
                source = work/'volatile.c'
                output = work/(case['id']+'-O'+opt+'.mlir')
                source.write_text(case['source']+'\n', encoding='utf-8')
                try:
                    built = execute([str(compiler),'build',str(source),*common,'--opt-level',opt,
                        '--target','mlir','-o',str(output)],cwd=work,env=dict(os.environ,PATH=''),
                        timeout=30,memory_limit=512*1024**2)
                    assert built.returncode == 0, built.stdout+built.stderr
                    ir = output.read_text(encoding='utf-8')
                    loads = re.findall(r'\bllvm\.load\s+volatile\b[^\n]*->\s*i32\b',ir)
                    assert len(loads) == case['volatile_loads'], ir
                    row.update(passed=True, volatile_loads=len(loads), seconds=built.elapsed_seconds,
                        peak_commit_bytes=built.peak_memory_bytes)
                except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                    row['error'] = str(error)
                report['results'].append(row)
                print(('PASS ' if row['passed'] else 'FAIL ')+row['id']+' O'+opt, flush=True)
    unchanged = before == fingerprints(compiler, MANIFEST)
    if settings.frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/c11.stx'])
    report['inputs_unchanged'] = report['inputs_unchanged'] and unchanged and source_hash == hashlib.sha256(source_path.read_bytes()).hexdigest()
    report['sha256'][source_path.relative_to(ROOT).as_posix()] = source_hash
    report['passed'] = sum(row['passed'] for row in report['results'])
    report['total'] = len(report['results'])
    settings.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f"{report['passed']}/{report['total']} generic checks; inputs unchanged: {report['inputs_unchanged']}", flush=True)
    return int(status != 0 or not report['inputs_unchanged'] or report['passed'] != report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
