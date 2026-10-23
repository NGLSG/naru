"""Run the complete C11 plan gates; missing features are failures, never skips.

This is an acceptance queue, not a language coverage percentage. Each suite
uses Naru's in-process backend and its own independent reference checks.
Without a current frozen compiler the final two-mode gate remains incomplete.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

from frozen_snapshot import validate_frozen
from rule_dependencies import c11_rule_inputs

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT/'tests/c11/support-plan.json'


def snapshot(compilers: list[Path]) -> dict[str, str]:
    paths = {PLAN, Path(__file__).resolve(), *compilers,
        *c11_rule_inputs(),
        *sorted(p for p in (ROOT/'tests/c11').rglob('*') if p.is_file()),
        *sorted((ROOT/'tests').glob('c11_*.py')),
        ROOT/'tests/native_process.py', ROOT/'tests/frozen_snapshot.py',
        ROOT/'tests/allocation.py', ROOT/'tests/name_scope.py'}
    for compiler in compilers:
        paths.add(compiler.parent/'naru_mlir_backend.dll')
        paths.update(path for path in (compiler.parent/'runtime/clang').rglob('*') if path.is_file())
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def load_plan() -> tuple[dict, list[dict]]:
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    items = [item for phase in plan['phases'] for item in phase['work_items']]
    ids = {item['id'] for item in items}
    if len(ids) != len(items):
        raise ValueError('Duplicate C11 work item')
    batches = plan['execution']['batches']
    if len({batch['id'] for batch in batches}) != len(batches):
        raise ValueError('Duplicate C11 delivery batch')
    allocated = [item for batch in batches for item in batch['work_items']]
    if len(allocated) != len(set(allocated)):
        raise ValueError('A C11 work item must belong to exactly one delivery batch')
    if set(allocated) != ids:
        raise ValueError('Delivery batches must account for every C11 work item')
    suites = plan['execution']['suites']
    if len({suite['id'] for suite in suites}) != len(suites):
        raise ValueError('Duplicate C11 gate suite')
    for suite in suites:
        path = (ROOT/suite['runner']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('Missing or external C11 gate runner: '+suite['runner'])
    for item in items:
        if item['status'] not in ('pending', 'in_progress', 'complete'):
            raise ValueError('Unknown work item status: '+item['id'])
        if item['status'] == 'complete' and (item.get('remaining') or not item.get('acceptance_evidence')):
            raise ValueError('Completed work requires empty remaining and reviewed acceptance_evidence: '+item['id'])
    return plan, items


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reuse_dynamic(path: Path, compiler: Path, suites: list[dict], current: dict[str, str]) -> list[dict]:
    previous = json.loads(path.read_text(encoding='utf-8'))
    if previous.get('modes') != ['dynamic'] or previous.get('inputs_unchanged') is not True:
        raise ValueError('Reuse requires an unchanged complete dynamic gate report')
    if previous.get('sha256') != current:
        raise ValueError('Dynamic gate inputs changed; run the dynamic suites again')
    rows = previous.get('results', [])
    if [(row.get('mode'), row.get('suite')) for row in rows] != [('dynamic', suite['id']) for suite in suites]:
        raise ValueError('Dynamic report does not contain the complete current suite queue')
    result = []
    for original, suite in zip(rows, suites):
        row = dict(original)
        report_path = Path(row['report'])
        log_path = Path(row['log'])
        command = [sys.executable, '-u', str(ROOT/suite['runner']),
            '--compiler', str(compiler), '--report', str(report_path), *suite.get('arguments', [])]
        if row.get('command') != command:
            raise ValueError('Reused suite command differs: '+suite['id'])
        if row.get('report_sha256') != digest(report_path) or row.get('log_sha256') != digest(log_path):
            raise ValueError('Reused suite artifacts changed: '+suite['id'])
        details = json.loads(report_path.read_text(encoding='utf-8'))
        checks = details['results']
        count = sum(check['passed'] for check in checks)
        unchanged = details.get('inputs_unchanged') is True
        passed = row.get('exit') == 0 and bool(checks) and count == len(checks) and unchanged
        if (row.get('passed'), row.get('checks_passed'), row.get('checks_total'), row.get('inputs_unchanged')) != (passed, count, len(checks), unchanged):
            raise ValueError('Reused suite outcome differs: '+suite['id'])
        row['reused_from'] = str(path.resolve())
        print('REUSE dynamic '+suite['id'], flush=True)
        result.append(row)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen-compiler', type=Path)
    parser.add_argument('--reuse-dynamic-report', type=Path,
        help='Reuse a complete dynamic run only when all input and suite-artifact hashes still match')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--report', type=Path, default=ROOT/'target/c11-full-support.json')
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 64:
        parser.error('--jobs must be 1..64')
    if args.reuse_dynamic_report and not args.frozen_compiler:
        parser.error('--reuse-dynamic-report requires --frozen-compiler')
    plan, items = load_plan()
    modes = [('dynamic', args.compiler.resolve())]
    frozen = None
    if args.frozen_compiler:
        compiler = args.frozen_compiler.resolve()
        frozen = validate_frozen(compiler, core=args.compiler.resolve(), required_rules=[ROOT/'dialects/c11.stx'])
        modes.append(('frozen', compiler))
    before = snapshot([compiler for _, compiler in modes])
    reused = reuse_dynamic(args.reuse_dynamic_report.resolve(), args.compiler.resolve(),
        plan['execution']['suites'], snapshot([args.compiler.resolve()])) if args.reuse_dynamic_report else []
    reused_hash = digest(args.reuse_dynamic_report.resolve()) if reused else None
    directory = ROOT/'target/c11-full-support'/uuid.uuid4().hex
    directory.mkdir(parents=True)
    started = time.perf_counter()

    def run(mode: str, compiler: Path, suite: dict) -> dict:
        report_path = directory/(mode+'-'+suite['id']+'.json')
        log_path = directory/(mode+'-'+suite['id']+'.log')
        command = [sys.executable, '-u', str(ROOT/suite['runner']),
            '--compiler', str(compiler), '--report', str(report_path), *suite.get('arguments', [])]
        if mode == 'frozen':
            command.append('--frozen')
        print('START '+mode+' '+suite['id'], flush=True)
        begin = time.perf_counter()
        row = dict(mode=mode, suite=suite['id'], command=command, report=str(report_path), log=str(log_path), passed=False)
        try:
            with log_path.open('w', encoding='utf-8') as stream:
                process = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    timeout=suite.get('timeout_seconds', 2400))
            row.update(exit=process.returncode, seconds=time.perf_counter()-begin)
            details = json.loads(report_path.read_text(encoding='utf-8'))
            results = details['results']
            count = sum(result['passed'] for result in results)
            row.update(checks_passed=count, checks_total=len(results), inputs_unchanged=details.get('inputs_unchanged', False))
            row['passed'] = process.returncode == 0 and bool(results) and count == len(results) and row['inputs_unchanged'] is True
            if mode == 'frozen':
                row['passed'] = row['passed'] and details.get('frozen_provenance') == frozen
            if not row['passed']:
                row['error'] = log_path.read_text(encoding='utf-8', errors='replace')[-6000:]
        except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
            row.update(error=str(error), seconds=time.perf_counter()-begin)
        if report_path.is_file():
            row['report_sha256'] = digest(report_path)
        if log_path.is_file():
            row['log_sha256'] = digest(log_path)
        print(('PASS ' if row['passed'] else 'FAIL ')+mode+' '+suite['id'], flush=True)
        return row

    requests = [(mode, compiler, suite) for mode, compiler in modes if mode != 'dynamic' or not reused
        for suite in plan['execution']['suites']]
    rows = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        pending = {executor.submit(run, *request): index for index, request in enumerate(requests)}
        for future in as_completed(pending):
            rows[pending[future]] = future.result()
    results = reused + [rows[index] for index in range(len(requests))]
    unchanged = before == snapshot([compiler for _, compiler in modes])
    if reused:
        unchanged = unchanged and reused_hash == digest(args.reuse_dynamic_report.resolve()) and all(
            row['report_sha256'] == digest(Path(row['report'])) and row['log_sha256'] == digest(Path(row['log']))
            for row in reused)
    if frozen:
        unchanged = unchanged and frozen == validate_frozen(args.frozen_compiler.resolve(), core=args.compiler.resolve(), required_rules=[ROOT/'dialects/c11.stx'])
    outstanding = [item['id'] for item in items if item['status'] != 'complete']
    passed = sum(row['passed'] for row in results)
    ready = passed == len(results) and unchanged and not outstanding and frozen is not None
    report = dict(format=1, target=plan['target'], standard=plan['standard'],
        full_c11_conformance_claimed=False, full_support_acceptance_ready=ready,
        coverage_percentage=None, jobs=args.jobs, seconds=time.perf_counter()-started,
        modes=[mode for mode, _ in modes], frozen_provenance=frozen,
        passed=passed, total=len(results), inputs_unchanged=unchanged, sha256=before,
        pending_work_items=outstanding, missing_frozen_acceptance=frozen is None, results=results)
    if reused:
        report['reused_dynamic_report'] = str(args.reuse_dynamic_report.resolve())
        report['reused_dynamic_report_sha256'] = reused_hash
    args.report.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2)+'\n'
    (directory/'summary.json').write_text(payload, encoding='utf-8')
    args.report.write_text(payload, encoding='utf-8')
    print(f'{passed}/{len(results)} suites; {len(outstanding)} work items pending; inputs unchanged: {unchanged}', flush=True)
    return int(not ready)


if __name__ == '__main__':
    raise SystemExit(main())
