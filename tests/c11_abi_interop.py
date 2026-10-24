"""Deferred Windows x64 C aggregate ABI interoperability with real C objects.

This runner is never used by the compiler. Each configured independent C
compiler supplies a pure-C baseline, a foreign callee and a foreign caller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from c11_conformance import ROOT, fingerprints
from frozen_snapshot import validate_frozen
from native_process import execute

MANIFEST = ROOT/'tests/c11/abi-interop.json'


def fingerprint(compiler: Path) -> dict[str, str]:
    result = fingerprints(compiler, MANIFEST)
    result[Path(__file__).relative_to(ROOT).as_posix()] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return result


def reference_object(driver: Path, source: Path, output: Path, opt: str, environment: dict[str, str], clang_flags: list[str]) -> None:
    if driver.name.lower() == 'cl.exe':
        command = [str(driver), '/nologo', '/c', '/std:c11', '/MT', '/Od' if opt == '0' else '/O2',
                   '/Fo'+str(output), str(source)]
    else:
        command = [str(driver), '-target', 'x86_64-pc-windows-msvc', '-std=c11', '-pedantic-errors',
                   *clang_flags, '-fms-runtime-lib=static', '-O'+opt, '-c', str(source), '-o', str(output)]
    checked = subprocess.run(command, cwd=source.parent, env=environment, capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stdout+checked.stderr


def reference_link(driver: Path, objects: list[Path], output: Path) -> None:
    checked = subprocess.run([str(driver), '-target', 'x86_64-pc-windows-msvc', '-fuse-ld=lld',
        '-fms-runtime-lib=static', *map(str, objects), '-o', str(output)], cwd=output.parent,
        capture_output=True, text=True, timeout=30)
    assert checked.returncode == 0, checked.stdout+checked.stderr


def assert_answer(path: Path, expected: int) -> None:
    native = execute([str(path)], cwd=path.parent, timeout=3, memory_limit=64*1024**2)
    assert (native.returncode, native.stdout) == (expected, ''), str(native)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--reference', type=Path, help='Independent Windows-target Clang object compiler/linker')
    parser.add_argument('--msvc', type=Path, help='Also accept against this cl.exe; Clang only links its objects')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--opt', choices=['0', '2'], action='append')
    parser.add_argument('--case', action='append')
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-abi-interop.json')
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    reference = args.reference or shutil.which('clang.exe')
    if not reference:
        parser.error('An independent Clang compiler/linker is required')
    reference = Path(reference).resolve()
    if reference.name.lower() == 'cl.exe':
        parser.error('--reference must be Clang; supply MSVC through --msvc')
    drivers = [reference] + ([args.msvc.resolve()] if args.msvc else [])
    corpus = json.loads(MANIFEST.read_text(encoding='utf-8'))
    case_ids = {case['id'] for case in corpus['cases']}
    if len(case_ids) != len(corpus['cases']) or any(not re.fullmatch(r'[a-z0-9-]+', item) for item in case_ids):
        parser.error('Invalid or duplicate corpus case identity')
    if args.case and set(args.case)-case_ids:
        parser.error('Unknown case')
    cases = [case for case in corpus['cases'] if not args.case or case['id'] in args.case]
    before = fingerprint(compiler)
    foreign_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in drivers}
    rules = [] if args.frozen else ['--rules', str(ROOT/'dialects/c11.stx')]
    frozen = validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/c11.stx']) if args.frozen else None
    discovered = execute([str(compiler), 'eval', *rules, '--expr', 'env.entries(headers.toolchain(env.empty()))'],
        cwd=ROOT, env=dict(os.environ, PATH=''), timeout=10)
    assert discovered.returncode == 0, discovered.stdout+discovered.stderr
    target = dict(json.loads(discovered.stdout))
    environment = dict(os.environ)
    environment['INCLUDE'] = ';'.join(target['include_paths'])
    common = [*rules, '--frontend', 'c11.frontend', '--entry', 'c11.item', '--unit', 'program',
        '--relation', 'c11.emit_program', '--runtime', 'crt-static', '--rule-depth', '1024',
        '--rule-budget', '100000000', '--parse-budget', '100000000']
    rows = []
    with tempfile.TemporaryDirectory(prefix='naru C11 aggregate ABI ') as directory:
        work = Path(directory)
        for case in cases:
            for opt in args.opt or ['0', '2']:
                for driver_index, driver in enumerate(drivers):
                    case_dir = work/(case['id']+'-O'+opt+'-ref'+str(driver_index))
                    case_dir.mkdir()
                    caller = case_dir/'caller.c'
                    provider = case_dir/'provider.c'
                    caller.write_text(case['declarations']+'\n'+case['caller']+'\n', encoding='utf-8')
                    provider.write_text(case['declarations']+'\n'+case['provider']+'\n', encoding='utf-8')
                    caller_obj, provider_obj = case_dir/'caller-ref.obj', case_dir/'provider-ref.obj'
                    baseline_error = None
                    try:
                        reference_object(driver, caller, caller_obj, opt, environment, case.get('reference_flags', []))
                        reference_object(driver, provider, provider_obj, opt, environment, case.get('reference_flags', []))
                        baseline = case_dir/'baseline.exe'
                        reference_link(reference, [caller_obj, provider_obj], baseline)
                        assert_answer(baseline, case.get('exit', 42))
                    except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                        baseline_error = str(error)
                    for direction in ['naru-caller', 'naru-callee']:
                        row = dict(id=case['id'], opt=opt, reference=str(driver), direction=direction,
                            passed=False, reference_validated=baseline_error is None,
                            reference_flags=case.get('reference_flags', []))
                        phase = 'reference-baseline'
                        try:
                            assert baseline_error is None, baseline_error
                            source = caller if direction == 'naru-caller' else provider
                            artifact = case_dir/(direction+('.exe' if direction == 'naru-caller' else '.obj'))
                            report = case_dir/(direction+'-build.json')
                            command = [str(compiler), 'build', str(source), *common, '--opt-level', opt,
                                '--target', 'exe' if direction == 'naru-caller' else 'object',
                                '-o', str(artifact), '--report', str(report)]
                            if direction == 'naru-caller':
                                command.extend(['--link-object', str(provider_obj)])
                            phase = 'naru-compile'
                            built = execute(command, cwd=case_dir, env=dict(os.environ, PATH=''),
                                timeout=30, memory_limit=512*1024**2)
                            assert built.returncode == 0, built.stdout+built.stderr
                            info = json.loads(report.read_text(encoding='utf-8'))
                            assert info['backend'] == 'in-process' and info['processes_spawned'] == 0, info
                            row.update(seconds=built.elapsed_seconds, peak_commit_bytes=built.peak_memory_bytes,
                                foreign_object_sha256=hashlib.sha256((provider_obj if direction == 'naru-caller' else caller_obj).read_bytes()).hexdigest())
                            phase = 'foreign-caller-link'
                            if direction == 'naru-callee':
                                program = case_dir/'foreign-caller.exe'
                                reference_link(reference, [caller_obj, artifact], program)
                            else:
                                program = artifact
                            phase = 'mixed-runtime'
                            assert_answer(program, case.get('exit', 42))
                            row['passed'] = True
                        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                            row.update(failure_phase=phase, error=str(error)[-4000:])
                        rows.append(row)
                        print(('PASS ' if row['passed'] else 'FAIL ')+case['id']+' O'+opt+' '+driver.name+' '+direction+
                            ('' if row['passed'] else ': '+row['error'][-700:]), flush=True)
    unchanged = before == fingerprint(compiler) and all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in foreign_hashes.items())
    if frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/c11.stx'])
    passed = sum(row['passed'] for row in rows)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(dict(target=corpus['target'], target_facts=target, passed=passed,
        total=len(rows), full_c11_conformance_claimed=False, scope=corpus['scope'], results=rows,
        sha256=before, reference_sha256=foreign_hashes, frozen_provenance=frozen, inputs_unchanged=unchanged),
        ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f'{passed}/{len(rows)} mixed compiler ABI checks; inputs unchanged: {unchanged}', flush=True)
    return int(passed != len(rows) or not unchanged)


if __name__ == '__main__':
    raise SystemExit(main())
