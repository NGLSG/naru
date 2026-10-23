"""Acceptance fingerprints cover loaded imports and exclude unrelated dialects."""
import json
from pathlib import Path
import tempfile

from rule_dependencies import ROOT, c11_rule_inputs, rule_dependencies


def main() -> int:
    checks = []
    def check(name, action):
        try:
            action()
            checks.append(dict(name=name, passed=True))
        except (AssertionError, ValueError, OSError) as error:
            checks.append(dict(name=name, passed=False, error=str(error)))
        print(('PASS ' if checks[-1]['passed'] else 'FAIL ')+name)

    def actual_graph():
        lock = json.loads((ROOT/'examples/c11/Naru.lock').read_text(encoding='utf-8'))
        expected = {(ROOT/'examples/c11'/row['path']).resolve() for row in lock['rules']}
        assert set(rule_dependencies([ROOT/'dialects/c11.stx'])) == expected
        assert expected <= set(c11_rule_inputs())
        assert ROOT/'dialects/c11-composed.stx' in c11_rule_inputs()
        assert ROOT/'dialects/basic.stx' not in c11_rule_inputs()
    check('C11 imports match the compiler lock and include its overlay', actual_graph)

    with tempfile.TemporaryDirectory(prefix='naru rule dependency checks ') as directory:
        work = Path(directory)
        entry, imported, unrelated = [work/(name+'.stx') for name in ['entry','imported','unrelated']]
        entry.write_text('mod entry;\nuse imported;\n',encoding='utf-8')
        imported.write_text('mod imported;\nuse entry;\n',encoding='utf-8')
        unrelated.write_text('mod unrelated;\n',encoding='utf-8')
        def cycles():
            assert set(rule_dependencies([entry],work)) == {entry,imported}
        check('cycles retain all imported modules without unrelated files', cycles)
        def quoted_imports():
            entry.write_text('mod entry;\nuse imported;\n// use missing;\n/* use missing; */\n'
                'syntax item `use missing;` => "use missing;";\n',encoding='utf-8')
            assert set(rule_dependencies([entry],work)) == {entry,imported}
        check('comments patterns and strings do not create imports', quoted_imports)
        def missing_import():
            entry.write_text('mod entry;\nuse missing;\n',encoding='utf-8')
            try:
                rule_dependencies([entry],work)
            except ValueError:
                return
            raise AssertionError('Missing imported input was ignored')
        check('missing imports fail closed', missing_import)
    passed = sum(row['passed'] for row in checks)
    (ROOT/'target/rule-dependency-checks.json').write_text(json.dumps(dict(passed=passed,total=len(checks),results=checks),indent=2)+'\n',encoding='utf-8')
    return int(passed != len(checks))


if __name__ == '__main__':
    raise SystemExit(main())
