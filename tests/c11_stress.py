"""C11 acceptance gate: system headers/CRT, mandatory features and unchanged real projects.

Any missing feature, diagnostic, timeout or crash is a failure. This suite does
not turn unimplemented cases into expected-failure passes. Clang is used only
as an independent test oracle; Naru itself runs without PATH or child processes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from native_process import execute
from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests/c11'

def fingerprints(compiler: Path) -> dict[str, str]:
    paths = [Path(__file__).resolve(), *c11_rule_inputs(),
             *sorted(p for p in DATA.rglob('*') if p.is_file())]
    result = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    result['compiler:'+str(compiler)] = hashlib.sha256(compiler.read_bytes()).hexdigest()
    backend = compiler.parent/'naru_mlir_backend.dll'
    if backend.is_file(): result['backend:'+str(backend)] = hashlib.sha256(backend.read_bytes()).hexdigest()
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'target/naru.exe')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--frozen', action='store_true', help='Use the compiler\'s frozen C11 group; only explicit project extensions are loaded')
    parser.add_argument('--case', action='append', help='Run selected cases by name')
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--memory-mib', type=int, default=2048)
    parser.add_argument('--report', type=Path, default=ROOT / 'target/c11-stress.json')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    before = fingerprints(compiler)
    reference = args.reference or shutil.which('clang.exe')
    if not reference:
        raise SystemExit('A reference Clang is required to validate the fixtures; it is not used by Naru.')
    reference = str(Path(reference).resolve())
    projects = json.loads((DATA / 'projects/sources.json').read_text(encoding='utf-8'))
    for project in projects:
        for file in project['files']:
            path = DATA / 'projects' / project['name'] / file['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != file['sha256']:
                raise SystemExit(f'Upstream source fingerprint mismatch: {path}')
    cases = []
    for name in ('scalar', 'system_io', 'declarators', 'initializers', 'nested_initializers', 'control', 'generic', 'varargs', 'layout'):
        cases.append((name, [DATA / 'cases' / (name + '.c')], 'system CRT: 42\n' if name == 'system_io' else ''))
    cases.append(('multiple_units', [DATA / 'cases/multiple_main.c', DATA / 'cases/multiple_helper.c'], ''))
    cases.append(('tinyexpr', [DATA / 'projects/tinyexpr/naru_stress_main.c', DATA / 'projects/tinyexpr/tinyexpr.c'], ''))
    cases.append(('cjson', [DATA / 'projects/cjson/naru_stress_main.c', DATA / 'projects/cjson/cJSON.c'], ''))
    all_cases_count = len(cases)
    if args.case:
        names = {case[0] for case in cases}
        unknown = set(args.case) - names
        if unknown:
            raise SystemExit('Unknown cases: ' + ', '.join(sorted(unknown)))
        cases = [case for case in cases if case[0] in args.case]
    results = []
    with tempfile.TemporaryDirectory(prefix='naru C11 stress ') as directory:
        work = Path(directory)
        for name, sources, stdout in cases:
            record = {'name': name, 'sources': [str(source) for source in sources], 'passed': False,
                      'expected_exit': 42, 'expected_stdout': stdout, 'naru_process_limit': 1}
            # TinyExpr deliberately stores function addresses in const void*.
            # Retain upstream bytes; select the host extension explicitly.
            record['extensions'] = ['function-pointer-interop'] if name == 'tinyexpr' else []
            started = time.perf_counter()
            stage = 'reference build'
            compilations = []
            try:
                ref_exe = work / (name + '-reference.exe')
                oracle = subprocess.run([reference, '-std=c11', '-O2', '-fuse-ld=lld', '-fms-runtime-lib=static',
                                         *map(str, sources), '-o', str(ref_exe)], cwd=work,
                                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=args.timeout)
                assert oracle.returncode == 0, oracle.stdout + oracle.stderr
                reference_run = execute([str(ref_exe)], cwd=work, timeout=10)
                assert reference_run.returncode == 42 and reference_run.stdout == stdout, str(reference_run)
                record['reference_validated'] = True
                stage = 'Naru compilation'
                common = ([] if args.frozen else ['--rules', str(ROOT / 'dialects/c11.stx')])+['--frontend', 'c11.frontend',
                          '--entry', 'c11.item', '--relation', 'c11.emit_program', '--unit', 'program',
                          '--runtime', 'crt-static', '--opt-level', '2', '--rule-budget', '100000000', '--parse-budget', '100000000',
                          '--rule-depth', '1024']
                if name == 'tinyexpr':
                    common += ['--rules', str(ROOT / 'dialects/c11/function-pointer-interop.stx')]
                objects = []
                # Every Naru translation unit is compiled by the selected rules.
                # The reference compiler's objects are never supplied to Naru.
                for index, source in enumerate(sources[1:], 1):
                    object_file = work / f'{name}-{index}.obj'
                    command = [str(compiler), 'build', str(source), *common, '--target', 'object', '-o', str(object_file)]
                    result = execute(command, cwd=work, env=dict(os.environ, PATH=''), timeout=args.timeout,
                                     memory_limit=args.memory_mib * 1024**2)
                    compilations.append({'source': str(source), 'seconds': result.elapsed_seconds, 'peak_commit_bytes': result.peak_memory_bytes, 'exit': result.returncode})
                    assert result.returncode == 0, f'compiler exit {result.returncode}: ' + result.stdout + result.stderr
                    objects.extend(['--link-object', str(object_file)])
                exe = work / (name + '-naru.exe')
                command = [str(compiler), 'build', str(sources[0]), *common, '--target', 'exe', '-o', str(exe), *objects]
                result = execute(command, cwd=work, env=dict(os.environ, PATH=''), timeout=args.timeout,
                                 memory_limit=args.memory_mib * 1024**2)
                compilations.append({'source': str(sources[0]), 'seconds': result.elapsed_seconds, 'peak_commit_bytes': result.peak_memory_bytes, 'exit': result.returncode})
                record['compilations'] = compilations
                assert result.returncode == 0, f'compiler exit {result.returncode}: ' + result.stdout + result.stderr
                stage = 'Naru execution'
                native = execute([str(exe)], cwd=work, timeout=10)
                assert native.returncode == 42 and native.stdout == stdout, str(native)
                record['passed'] = True
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                record['failed_stage'] = stage
                record['error'] = str(error)[:12000]
                if compilations:
                    record['compilations'] = compilations
            record['seconds'] = time.perf_counter() - started
            results.append(record)
            print(('PASS ' if record['passed'] else 'FAIL ') + name + ('' if record['passed'] else ': ' + record['failed_stage'] + ': ' + record['error'].split('\n')[0]), flush=True)
    passed = sum(result['passed'] for result in results)
    unchanged = before == fingerprints(compiler)
    if args.frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'dialects/c11.stx'])
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'format': 1, 'compiler': str(compiler), 'reference': reference,
        'system_headers_required': True, 'system_crt_required': True, 'projects': projects,
        'sha256': before, 'inputs_unchanged': unchanged, 'frozen_provenance': frozen,
        'passed': passed, 'total': len(results), 'all_selected_passed': unchanged and passed == len(results),
        'full_suite_passed': unchanged and len(results) == all_cases_count and passed == all_cases_count,
        'full_c11_conformance_claimed': False, 'results': results}, indent=2) + '\n', encoding='utf-8')
    print(f'\n{passed}/{len(results)} C11 stress cases passed; report: {args.report}')
    return int(not unchanged or passed != len(results))

if __name__ == '__main__':
    raise SystemExit(main())
