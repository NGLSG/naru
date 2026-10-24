"""Immutable name facts and caller-defined namespace policy, dynamic or frozen."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from frozen_snapshot import validate_frozen
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / 'dialects/name_scope.stx'
FIXTURE = ROOT / 'tests/fixtures/name_scope_contract.stx'
CASES = [
    ('independent namespaces', 'distinct_namespaces()', '[1,1,1,1]', 0),
    ('child shadowing preserves the parent and local facts', 'parent_shadowing()', '[1,1,1,1,1,1,1,1]', 0),
    ('completion preserves identity and the earlier snapshot', 'same_declaration_completion()', '[1,1,1,1,1]', 0),
    ('sibling prototype frames have distinct identities', 'sibling_prototypes()', '[1,1,1,1]', 0),
    ('caller policy permits parent namespace shadowing', 'own_ordinary_policy()', '[1,1]', 0),
    ('opaque namespaces names and payloads retain snapshots', 'snapshot_is_stable()', '[1,1,1]', 0),
    ('caller policy rejects a same-frame duplicate', 'duplicate_ordinary()', 'duplicate name in the current ordinary namespace', 1),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'target/naru.exe')
    parser.add_argument('--frozen', action='store_true',
                        help='Require name_scope in the frozen snapshot; load only the test fixture dynamically')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    compiler = args.compiler.resolve()
    provenance_args = dict(core=ROOT / 'target/naru.exe', required_rules=[LIBRARY])
    # A frozen run must exercise the native library. A missing/stale library is
    # an error; it must never be silently replaced by its dynamic STX copy.
    frozen = validate_frozen(compiler, **provenance_args) if args.frozen else None
    paths = [compiler, compiler.parent / 'naru_mlir_backend.dll', Path(__file__),
             FIXTURE, LIBRARY, ROOT / 'dialects/Naru.toml']
    before = {str(path): digest(path) for path in paths}
    rules = ([] if args.frozen else ['--rules', str(LIBRARY)]) + ['--rules', str(FIXTURE)]
    results = []
    with tempfile.TemporaryDirectory(prefix='naru name scope contracts ') as work:
        for name, expression, expected, code in CASES:
            row = {'name': name, 'passed': False}
            try:
                run = execute([str(compiler), 'eval', *rules, '--expr',
                               'name_scope_contract.' + expression],
                              cwd=Path(work), env=dict(os.environ, PATH=''),
                              timeout=30, memory_limit=128 * 1024**2)
                output = run.stdout + run.stderr
                assert run.returncode == code, output
                assert (expected in output if code else
                        run.stdout.strip().replace(' ', '') == expected), output
                row.update(passed=True, seconds=run.elapsed_seconds,
                           peak_commit_bytes=run.peak_memory_bytes)
            except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
                row['error'] = str(error)[-4000:]
            results.append(row)
            print(('PASS ' if row['passed'] else 'FAIL ') + name +
                  ('' if row['passed'] else ': ' + row['error']), flush=True)
    unchanged = before == {str(path): digest(path) for path in paths}
    if args.frozen:
        unchanged = unchanged and frozen == validate_frozen(compiler, **provenance_args)
    passed = sum(row['passed'] for row in results)
    report = args.report or ROOT / 'target' / ('name-scope-frozen.json' if args.frozen else 'name-scope.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({'compiler': str(compiler),
                                 'mode': 'frozen' if args.frozen else 'dynamic',
                                 'passed': passed, 'total': len(results),
                                 'inputs_unchanged': unchanged, 'frozen_provenance': frozen,
                                 'sha256': before, 'results': results}, indent=2) + '\n',
                      encoding='utf-8')
    print(f'{passed}/{len(results)} name scope checks passed; inputs unchanged: {unchanged}')
    return int(passed != len(results) or not unchanged)


if __name__ == '__main__':
    raise SystemExit(main())
