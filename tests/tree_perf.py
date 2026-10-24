"""Compare generic rule traversal and iteration allocation with identical rules.

This measures the compiler frontend, not generated program runtime performance.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    p.add_argument('--baseline', type=Path)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--report', type=Path, default=ROOT/'target/tree-performance.json')
    a = p.parse_args()
    if not 1 <= a.repeat <= 20:
        p.error('--repeat must be 1..20')
    binaries = {'current': a.compiler.resolve()}
    if a.baseline:
        binaries = {'baseline': a.baseline.resolve(), **binaries}
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    snapshots = {name: {'path': str(path), 'sha256': digest(path),
        'backend_sha256': digest(path.with_name('naru_mlir_backend.dll'))} for name, path in binaries.items()}
    if a.baseline:
        assert snapshots['baseline']['backend_sha256'] == snapshots['current']['backend_sha256']
    rules = [ROOT/'tests/fixtures/tree_perf.stx', ROOT/'dialects/tree.stx',
             ROOT/'tests/fixtures/iteration_contract.stx']
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in rules}
    cases = [('wide_20000', 'tree_perf.wide(20000)', '[20000,200010000]'),
             ('deep_4096', 'tree_perf.deep(4096)', '4097'),
             ('replace_scratch_20000x64', 'tree_perf.scratch(20000,64)', '[20000,64]'),
             ('sparse_unfold_100001', 'iteration_contract.sparse(100001)',
              '[0,10000,20000,30000,40000,50000,60000,70000,80000,90000,100000]'),
             ('replace_fold_30000x32', 'iteration_contract.fold_scratch(30000)', '[30000,32,496]'),
             ('shared_unfold_100000', 'iteration_contract.repeated(100000)', '[100000,1]')]
    results = []
    with tempfile.TemporaryDirectory(prefix='naru tree perf ') as work:
        for name, expression, expected in cases:
            record = {'name': name, 'expression': expression, 'result': expected}
            samples = {label: [] for label in binaries}
            # Alternate binaries to reduce ordering effects.
            for iteration in range(a.repeat):
                for label in (tuple(binaries) if iteration % 2 == 0 else tuple(reversed(binaries))):
                    run = execute([str(binaries[label]), 'eval', *[arg for path in rules for arg in ('--rules', str(path))],
                        '--expr', expression, '--rule-budget', '100000000'], cwd=work,
                        env=dict(os.environ, PATH=''), timeout=120, memory_limit=2*1024**3)
                    assert run.returncode == 0, run.stdout+run.stderr
                    assert run.stdout.strip().replace(' ', '') == expected, run.stdout+run.stderr
                    samples[label].append({'seconds': run.elapsed_seconds, 'peak_commit_bytes': run.peak_memory_bytes})
            for label in binaries:
                record[label] = {'samples': samples[label], 'median_seconds': statistics.median(s['seconds'] for s in samples[label]),
                    'peak_commit_bytes': max(s['peak_commit_bytes'] for s in samples[label])}
            if a.baseline:
                record['time_ratio'] = record['current']['median_seconds']/record['baseline']['median_seconds']
                record['memory_ratio'] = record['current']['peak_commit_bytes']/record['baseline']['peak_commit_bytes']
            results.append(record)
            if a.baseline:
                print(f"{name}: time ratio {record['time_ratio']:.3f}, memory ratio {record['memory_ratio']:.3f}", flush=True)
            else:
                print(f"PASS {name}: {record['current']['median_seconds']:.3f}s, {record['current']['peak_commit_bytes']/1024**2:.1f} MiB", flush=True)
    assert hashes == {str(path.relative_to(ROOT)): digest(path) for path in rules}, 'Rules changed during measurement'
    assert all(snapshots[label]['sha256'] == digest(path) for label, path in binaries.items()), 'Compiler changed during measurement'
    a.report.write_text(json.dumps({'format': 1, 'kind': 'compiler_rule_traversal', 'repeat': a.repeat,
        'same_rule_files': True, 'process_limit': 1, 'rule_sha256': hashes, 'binaries': snapshots, 'results': results}, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
