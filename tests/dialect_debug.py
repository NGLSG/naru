"""Adversarial dialect regressions; dynamic rules, bounded native processes.

Fixtures test observable semantics and required diagnostics, at O0 and O2.
The C fixtures also run through Clang as an independent semantic oracle.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import time

from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/dialects/regressions.json'


def rule_fingerprints() -> dict[str, str]:
    return {str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((ROOT / 'dialects').rglob('*.stx'))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dialect', action='append', choices=['b', 'pascal', 'c11'])
    parser.add_argument('--case', action='append')
    parser.add_argument('--opt', action='append', choices=['0', '2'])
    parser.add_argument('--report', type=Path, default=ROOT / 'target/dialect-debug.json')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--timeout', type=float, default=20)
    args = parser.parse_args()
    reference = args.reference or shutil.which('clang.exe')
    if reference is None:
        raise SystemExit('A reference Clang is required for the C11 dialect fixtures.')
    cases = json.loads(FIXTURES.read_text(encoding='utf-8'))
    if args.case and set(args.case) - {case['name'] for case in cases}:
        parser.error('Unknown fixture name')
    work = ROOT / 'target/dialect-debug'
    work.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / 'target/naru.exe'
    fingerprints = rule_fingerprints()
    results = []
    for case in cases:
        dialect = case['dialect']
        if args.dialect and dialect not in args.dialect:
            continue
        if args.case and case['name'] not in args.case:
            continue
        suffix = {'b': 'b', 'pascal': 'pas', 'c11': 'c'}[dialect]
        source = work / (case['name'] + '.' + suffix)
        content = (ROOT / case['source_file']).read_text(encoding='utf-8') if 'source_file' in case else case['source']
        source.write_text(content + '\n', encoding='utf-8')
        for opt in args.opt or ['0', '2']:
            record = dict(name=case['name'], dialect=dialect, opt=opt, passed=False)
            stage = 'compile'
            try:
                if dialect == 'c11' and 'reject' in case:
                    stage = 'reference diagnostic'
                    ref = subprocess.run([str(reference), '-std=c11', '-pedantic-errors',
                                          '-fsyntax-only', str(source)], cwd=work,
                                         capture_output=True, text=True, timeout=args.timeout)
                    if case.get('standard_constraint'):
                        record['standard_constraint'] = case['standard_constraint']
                        record['reference_validated'] = ref.returncode != 0
                        record['reference_disagreement'] = ref.returncode == 0
                    else:
                        assert ref.returncode != 0, 'Clang accepted the invalid fixture'
                        record['reference_validated'] = True
                    stage = 'compile'
                exe = work / (case['name'] + '-O' + opt + '.exe')
                common = ['--rules', str(ROOT / 'dialects' / (dialect + '.stx')),
                          '--frontend', dialect + '.frontend', '--runtime', 'crt-static',
                          '--opt-level', opt, '--rule-depth', '1024',
                          '--rule-budget', '10000000', '--parse-budget', '10000000']
                for extra in case.get('extra_rules', []):
                    common += ['--rules', str(ROOT / extra)]
                if case.get('check_only'):
                    common += ['--relation', 'analyze']
                elif dialect in ('b', 'c11'):
                    common += ['--unit', 'program', '--relation',
                               'c11.emit_program' if dialect == 'c11' else 'emit_program']
                command = [str(compiler), 'check' if case.get('check_only') else 'build', str(source), *common,
                           '--target', 'exe', '-o', str(exe)]
                build = execute(command, cwd=ROOT, env=dict(os.environ, PATH=''),
                                timeout=args.timeout, memory_limit=512 * 1024**2)
                record.update(compile_exit=build.returncode,
                              compile_seconds=round(build.elapsed_seconds, 4),
                              peak_commit_bytes=build.peak_memory_bytes)
                if 'reject' in case:
                    assert build.returncode != 0, 'Source requiring a diagnostic was accepted'
                    assert case['reject'] in build.stdout + build.stderr, build.stdout + build.stderr
                elif case.get('check_only'):
                    assert build.returncode == 0, build.stdout + build.stderr
                else:
                    assert build.returncode == 0, build.stdout + build.stderr
                    stage = 'execute'
                    native = execute([str(exe)], cwd=work, timeout=3, memory_limit=64 * 1024**2)
                    record.update(exit=native.returncode, stdout=native.stdout)
                    assert native.returncode == case.get('exit', 42), f'Wrong exit: {native.returncode}'
                    assert native.stdout == case.get('stdout', ''), repr(native.stdout)
                    if dialect == 'c11':
                        stage = 'reference'
                        oracle = work / (case['name'] + '-clang.exe')
                        ref = subprocess.run([str(reference), '-std=c11', '-O' + opt,
                                              '-fuse-ld=lld', '-fms-runtime-lib=static',
                                              str(source), '-o', str(oracle)], cwd=work,
                                             capture_output=True, text=True, timeout=args.timeout)
                        assert ref.returncode == 0, ref.stdout + ref.stderr
                        run = execute([str(oracle)], cwd=work, timeout=3)
                        assert (run.returncode, run.stdout) == (native.returncode, native.stdout), 'Clang disagreement'
                        record['reference_validated'] = True
                record['passed'] = True
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                record.update(stage=stage, error=str(error)[-5000:])
            results.append(record)
            print(f"{'PASS' if record['passed'] else 'FAIL'} {case['name']} O{opt}" +
                  ('' if record['passed'] else ': ' + record['error'][-650:]), flush=True)
    unchanged = rule_fingerprints() == fingerprints
    report = dict(generated_at=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                  compiler_sha256=hashlib.sha256(compiler.read_bytes()).hexdigest(),
                  fixture_sha256=hashlib.sha256(FIXTURES.read_bytes()).hexdigest(),
                  rule_sha256=fingerprints, process_limit=1, memory_limit_mib=512,
                  rules_unchanged=unchanged,
                  passed=unchanged and bool(results) and all(r['passed'] for r in results),
                  results=results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
