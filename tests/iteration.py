"""Lifetime contracts for batched unfold/fold state collection."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    inputs = [compiler, Path(__file__).resolve(), ROOT/'tests/native_process.py',
              ROOT/'tests/fixtures/iteration_contract.stx']
    fingerprint = lambda: {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    before = fingerprint()
    rules = [] if args.frozen else ['--rules', str(ROOT/'tests/fixtures/iteration_contract.stx')]
    cases = [
        ('terminal chunk is emitted', 'list.unfold("iteration_contract.stop",0,1)', '[7,8]', 0),
        ('malformed step shape is rejected', 'list.unfold("iteration_contract.malformed",0,10)', 'step must return', 1),
        ('malformed chunk is rejected', 'list.unfold("iteration_contract.malformed_chunk",0,10)', 'requires a list', 1),
        ('invalid continuation is rejected', 'list.unfold("iteration_contract.bad_truth",0,10)', 'integer truth value', 1),
        ('unfinished unfold respects its step budget', 'list.unfold("iteration_contract.forever",0,9000)', 'step budget exhausted', 1),
        ('output retains multiple shared historical states', 'iteration_contract.linked_check(3000)', '[3000,1,2,3000,4498500]', 0),
        ('current environment survives empty output chunks', 'iteration_contract.state(12000)', '[11999]', 0),
        ('older output survives later state replacement', 'iteration_contract.sparse(30001)', '[0,10000,20000,30000]', 0),
        ('growing output shares one borrowed value', 'iteration_contract.repeated(30000)', '[30000,1]', 0),
        ('nested unfolding retains only the final scratch value', 'iteration_contract.scratch_check(4000,32)', '[32,496]', 0),
        ('fold retains persistent environment indexes', 'iteration_contract.environment(2000)', '[1,2000,2000]', 0),
        ('fold replaces a nested scratch list', 'iteration_contract.fold_scratch(4000)', '[4000,32,496]', 0),
        ('fold retains shared accumulator tails', 'iteration_contract.fold_sharing(12000)', '[12000,11999,71994000]', 0),
        ('iterate retains shared state across recycled slots', 'iteration_contract.iterate_sharing(20000)', '[20000,20000,19999,199990000]', 0),
        ('empty fold returns its borrowed seed', 'list.fold("iteration_contract.sum",[],[42])', '[42]', 0),
    ]
    results = []
    with tempfile.TemporaryDirectory(prefix='naru iteration contracts ') as work:
        for label, expression, expected, code in cases:
            item = {'name': label, 'passed': False}
            try:
                run = execute([str(args.compiler.resolve()), 'eval', *rules, '--expr', expression,
                               '--rule-budget', '100000000'], cwd=work, env=dict(os.environ, PATH=''),
                              timeout=30, memory_limit=128*1024**2)
                item.update(returncode=run.returncode, seconds=run.elapsed_seconds,
                            peak_commit_bytes=run.peak_memory_bytes)
                assert run.returncode == code, f'exit {run.returncode}, expected {code}; peak {run.peak_memory_bytes} bytes\n'+run.stdout+run.stderr
                assert (expected in run.stdout+run.stderr if code else
                        run.stdout.strip().replace(' ', '') == expected), run.stdout+run.stderr
                item['passed'] = True
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                item['error'] = str(error)[-3000:]
            results.append(item)
            print(('PASS ' if item['passed'] else 'FAIL ')+label+
                  ('' if item['passed'] else ': '+item['error']), flush=True)
        item = {'name': 'discarded unfold/fold results retain IR across collections', 'passed': False}
        try:
            source = Path(work)/'iterations.nru'
            source.write_text('iterations 4500\n', encoding='utf-8')
            output = Path(work)/'iterations.mlir'
            run = execute([str(args.compiler.resolve()), 'emit', str(source), *rules,
                           '--rule-budget', '100000000', '-o', str(output)], cwd=work,
                          env=dict(os.environ, PATH=''), timeout=30, memory_limit=128*1024**2)
            item.update(returncode=run.returncode, seconds=run.elapsed_seconds,
                        peak_commit_bytes=run.peak_memory_bytes)
            assert run.returncode == 0, f'exit {run.returncode}, expected 0; peak {run.peak_memory_bytes} bytes\n'+run.stdout+run.stderr
            text = output.read_text(encoding='utf-8')
            assert text.count('"arith.constant"') == 9001, text[-2000:]
            assert text.count('"func.return"') == 1, text[-2000:]
            item['passed'] = True
        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
            item['error'] = str(error)[-3000:]
        results.append(item)
        print(('PASS ' if item['passed'] else 'FAIL ')+item['name']+
              ('' if item['passed'] else ': '+item['error']), flush=True)
    passed = sum(item['passed'] for item in results)
    unchanged = before == fingerprint()
    report = args.report or ROOT/'target'/('iteration-frozen.json' if args.frozen else 'iteration.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'passed': passed, 'total': len(results), 'results': results,
                                 'memory_limit_bytes':128*1024**2, 'inputs_unchanged':unchanged,
                                 'sha256':before}, indent=2)+'\n')
    print(f'{passed}/{len(results)} iteration lifetime checks passed; inputs unchanged: {unchanged}')
    return int(not unchanged or passed != len(results))


if __name__ == '__main__':
    raise SystemExit(main())
