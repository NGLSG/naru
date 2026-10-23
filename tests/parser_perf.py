"""Compare indexed parser throughput against a saved core on identical rules.
This measures the compiler frontend, not generated-program runtime.
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


def fingerprint(path):
    path = path.resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "backend_sha256": hashlib.sha256(path.with_name("naru_mlir_backend.dll").read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    p.add_argument('--baseline', type=Path, required=True)
    p.add_argument('--repeat', type=int, default=3)
    p.add_argument('--report', type=Path, default=ROOT/'target/parser-performance.json')
    a = p.parse_args()
    assert 1 <= a.repeat <= 20
    fingerprints = {"baseline": fingerprint(a.baseline), "current": fingerprint(a.compiler)}
    assert fingerprints['baseline']['backend_sha256'] == fingerprints['current']['backend_sha256']
    rules = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in [*(ROOT/'dialects').rglob('*.stx'), ROOT/'tests/fixtures/frontend_cache.stx']}
    records = []
    with tempfile.TemporaryDirectory(prefix='naru parser perf ') as directory:
        work = Path(directory)
        grammar = work/'wide.stx'
        grammar.write_text('mod wide;\nsyntax bench.expr `$n:int` => Number($n);\n'
            'syntax bench.expr[50,left] `$a:bench.expr + $b:bench.expr` => Add($a,$b);\n'
            'syntax bench.item `$e:bench.expr;` => Item($e);\n' +
            ''.join(f'syntax bench.expr `keyword{i}` => Number(0);\n'
                    f'syntax bench.expr[50,left] `$a:bench.expr op{i} $b:bench.expr` => Add($a,$b);\n'
                    for i in range(1000)), encoding='utf-8')
        wide = work/'wide.input'; wide.write_text('40+2;\n'*2000)
        nested = work/'nested.input'; nested.write_text('('*50+'42'+') a'*50+';')
        c = work/'main.c'; c.write_text('#include <stdio.h>\nint main(void){printf("%d\\n",42);return 42;}\n')
        cases = [
            ('2003_rules_2000_items', wide, ['--rules', str(grammar), '--entry', 'bench.item']),
            ('shared_recursive_prefixes', nested, ['--rules', str(ROOT/'tests/fixtures/frontend_cache.stx'), '--entry', 'cache.item']),
            ('system_stdio_frontend', c, ['--rules', str(ROOT/'dialects/c11.stx'), '--frontend', 'c11.frontend', '--entry', 'c11.item']),
        ]
        for name, source, options in cases:
            samples = {'baseline': [], 'current': []}; outputs = set()
            for _ in range(a.repeat):
                for label, compiler in [('baseline', a.baseline), ('current', a.compiler)]:
                    result = execute([str(compiler.resolve()), 'parse', str(source), *options,
                        '--rule-budget', '100000000', '--parse-budget', '100000000'],
                        cwd=work, env=dict(os.environ, PATH=''), timeout=120, memory_limit=4*1024**3)
                    assert result.returncode == 0, result.stdout+result.stderr
                    outputs.add(hashlib.sha256(result.stdout.encode()).hexdigest())
                    samples[label].append({'seconds': result.elapsed_seconds, 'peak_commit_bytes': result.peak_memory_bytes})
            assert len(outputs) == 1, f'{name}: baseline/current ASTs differ'
            record = {'name': name, 'result_sha256': next(iter(outputs)),
                      'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'options': options, 'grammar_sha256': hashlib.sha256(grammar.read_bytes()).hexdigest() if name == '2003_rules_2000_items' else None}
            for label, values in samples.items():
                record[label] = {'samples': values, 'median_seconds': statistics.median(v['seconds'] for v in values),
                                 'peak_commit_bytes': max(v['peak_commit_bytes'] for v in values)}
            record['time_ratio'] = record['current']['median_seconds']/record['baseline']['median_seconds']
            record['memory_ratio'] = record['current']['peak_commit_bytes']/record['baseline']['peak_commit_bytes']
            records.append(record)
            print(f"{name}: time {record['time_ratio']:.3f}x, commit {record['memory_ratio']:.3f}x", flush=True)
    assert fingerprints['baseline'] == fingerprint(a.baseline) and fingerprints['current'] == fingerprint(a.compiler)
    assert rules == {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in [*(ROOT/'dialects').rglob('*.stx'), ROOT/'tests/fixtures/frontend_cache.stx']}, 'rules changed during measurement'
    a.report.write_text(json.dumps({'format': 1, 'kind': 'compiler_frontend_parser', 'repeat': a.repeat,
        'same_rules_and_inputs': True, 'same_ast_results': True, 'compilers': fingerprints,
        'rule_sha256': rules, 'results': records}, indent=2)+'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
