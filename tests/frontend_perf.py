"""Compare compiler frontend time/peak commit on identical inputs and results.
Generated-program runtime performance is deliberately outside this benchmark.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, default=ROOT / 'target/naru.exe')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--report', type=Path, default=ROOT / 'target/frontend-performance.json')
    a = p.parse_args()
    assert 1 <= a.repeat <= 20
    cases = [('persistent_10000', 'tests/fixtures/frontend_infra.stx', 'frontend_infra.verify(10000)', '[1,1,1,1,1]'),
             ('nested_temporary_4000x64', 'tests/fixtures/frontend_infra.stx', 'frontend_infra.scratch(4000,64)', '[64,252000]'),
             ('system_stdio_preprocessing', 'dialects/c11.stx', 'size(c11.pp.preprocess("#include <stdio.h>\\n","<perf>",env.empty()))', None)]
    def fingerprint(binary):
        binary=binary.resolve()
        return {'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
                'backend_sha256':hashlib.sha256(binary.with_name('naru_mlir_backend.dll').read_bytes()).hexdigest()}
    def rule_fingerprints():
        paths=sorted([*(ROOT/'dialects').rglob('*.stx'),*(ROOT/'tests/fixtures').rglob('*.stx')])
        return {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    snapshots={'compiler':fingerprint(a.compiler),'baseline':fingerprint(a.baseline),'rules':rule_fingerprints()}
    assert snapshots['compiler']['backend_sha256']==snapshots['baseline']['backend_sha256'], 'Use identical backend DLLs to isolate frontend changes'
    results = []
    for name, rules, expression, expected in cases:
        item = {'name': name, 'expression': expression, 'rules': rules}
        outputs = []
        for label, binary in [('baseline', a.baseline.resolve()), ('current', a.compiler.resolve())]:
            samples = []
            for _ in range(a.repeat):
                r = execute([str(binary), 'eval', '--rules', str(ROOT/rules), '--expr', expression,
                             '--rule-budget', '100000000', '--parse-budget', '100000000'], cwd=ROOT,
                            env=dict(os.environ, PATH=''), timeout=120, memory_limit=4*1024**3)
                assert r.returncode == 0, r.stdout + r.stderr
                value = r.stdout.strip().replace(' ', '')
                if expected is not None:
                    assert value == expected, value
                outputs.append(value)
                samples.append({'seconds': r.elapsed_seconds, 'peak_commit_bytes': r.peak_memory_bytes})
            item[label] = {'samples': samples, 'median_seconds': statistics.median(x['seconds'] for x in samples),
                           'peak_commit_bytes': max(x['peak_commit_bytes'] for x in samples)}
        assert len(set(outputs)) == 1, outputs
        item['result'] = outputs[0]
        item['memory_ratio'] = item['current']['peak_commit_bytes']/item['baseline']['peak_commit_bytes']
        item['time_ratio'] = item['current']['median_seconds']/item['baseline']['median_seconds']
        results.append(item)
        print(f"{name}: time ratio {item['time_ratio']:.3f}, commit ratio {item['memory_ratio']:.3f}", flush=True)
    assert snapshots['compiler']==fingerprint(a.compiler) and snapshots['baseline']==fingerprint(a.baseline), 'Compiler changed during measurement'
    assert snapshots['rules']==rule_fingerprints(), 'Rules changed during measurement'
    a.report.write_text(json.dumps({'format': 1, 'kind': 'compiler_frontend', 'repeat': a.repeat,
        'same_rule_files_for_both_compilers': True, 'process_limit': 1, 'memory_limit_mib': 4096,
        'compiler': snapshots['compiler'], 'baseline': snapshots['baseline'], 'rule_sha256':snapshots['rules'], 'results': results}, indent=2)+'\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
