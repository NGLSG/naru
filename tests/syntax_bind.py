"""Lexical bind substitution in syntax constructors, dynamic and native AOT."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
from native_process import execute
from frozen_snapshot import validate_frozen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'target/naru.exe')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    frozen = validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'tests/fixtures/syntax_bind.stx']) if args.frozen else None
    rules = [] if args.frozen else ['--rules', str(ROOT / 'tests/fixtures/syntax_bind.stx')]
    cases = [
        ('local', 'syntax_bind.Pair(43,42)', None),
        ('shadow', 'syntax_bind.Pair(43,44)', None),
        ('nested', '[42,44,42]', None),
        ('discard', '42', None),
        ('repeated', '42', None),
        ('outer', '[43,85]', None),
        ('siblings', '[43,42,44]', None),
        ('mismatch', None, 'bind pattern does not match'),
        ('wildcard', None, 'unbound'),
        ('ignored', None, 'unbound'),
        ('omit', '42', None),
    ]
    results = []
    for name, expected, diagnostic in cases:
        tokens = [[1, name, '<syntax-bind>', 1, 1], [2, '42', '<syntax-bind>', 1, len(name) + 2]]
        expression = f'source.parse_tokens({json.dumps(tokens)},"bind.expr",env.empty(),"syntax_bind.commit")'
        try:
            result = execute([str(compiler), 'eval', *rules, '--expr', expression], cwd=ROOT,
                env=dict(os.environ, PATH=''), timeout=30, memory_limit=512 * 1024**2)
            output = result.stdout + result.stderr
            if diagnostic:
                assert result.returncode in (1, 2) and diagnostic in output, output
            else:
                assert result.returncode == 0, output
                assert result.stdout.strip().replace(' ', '') == '[' + expected + ']', output
            item = {'name': name, 'passed': True}
        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
            item = {'name': name, 'passed': False, 'error': str(error)}
        results.append(item)
        print(('PASS ' if item['passed'] else 'FAIL ') + name, flush=True)
    passed = sum(item['passed'] for item in results)
    if args.frozen:
        assert frozen == validate_frozen(compiler,core=ROOT/'target/naru.exe',required_rules=[ROOT/'tests/fixtures/syntax_bind.stx']), 'Frozen inputs changed during the suite'
    report = args.report or ROOT / ('target/syntax-bind-frozen.json' if args.frozen else 'target/syntax-bind.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'compiler': str(compiler), 'mode': 'frozen' if args.frozen else 'dynamic', 'frozen_provenance':frozen,
        'passed': passed, 'total': len(results), 'results': results}, indent=2) + '\n', encoding='utf-8')
    print(f'{passed}/{len(results)} syntax binding checks passed')
    return int(passed != len(results))


if __name__ == '__main__':
    raise SystemExit(main())
