"""C11 gate reuse must reject stale inputs, edited evidence and waived failures."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

from c11_full_support import ROOT, digest, reuse_dynamic


def main() -> int:
    compiler = ROOT/'target/naru.exe'
    suite = dict(id='pending-features', runner='tests/c11_support.py')
    checks = []
    with tempfile.TemporaryDirectory(prefix='naru full gate guard ') as directory:
        work = Path(directory)
        report = work/'suite.json'
        log = work/'suite.log'
        summary = work/'summary.json'

        def fixture():
            report.write_text(json.dumps(dict(inputs_unchanged=True,
                results=[dict(passed=True), dict(passed=False)])), encoding='utf-8')
            log.write_text('PASS implemented\nFAIL missing\n', encoding='utf-8')
            return dict(modes=['dynamic'], inputs_unchanged=True, sha256={'source':'original'},
                results=[dict(mode='dynamic', suite=suite['id'], report=str(report), log=str(log),
                    command=[sys.executable, '-u', str(ROOT/suite['runner']), '--compiler', str(compiler),
                        '--report', str(report)], exit=1, passed=False, checks_passed=1, checks_total=2,
                    inputs_unchanged=True, report_sha256=digest(report), log_sha256=digest(log))])

        def run(data, current=None):
            summary.write_text(json.dumps(data), encoding='utf-8')
            with contextlib.redirect_stdout(io.StringIO()):
                return reuse_dynamic(summary, compiler, [suite], current or {'source':'original'})

        def check(name, action):
            try:
                action()
                checks.append(dict(name=name, passed=True))
            except (AssertionError, ValueError, OSError, KeyError) as error:
                checks.append(dict(name=name, passed=False, error=str(error)))
            print(('PASS ' if checks[-1]['passed'] else 'FAIL ')+name, flush=True)

        def rejected(data, current=None):
            try:
                run(data, current)
            except (ValueError, OSError, KeyError):
                return
            raise AssertionError('Changed evidence was accepted')

        def retain_failure():
            rows = run(fixture())
            assert len(rows) == 1 and rows[0]['passed'] is False
            assert (rows[0]['checks_passed'], rows[0]['checks_total']) == (1, 2)
        check('known missing features remain failures on reuse', retain_failure)
        check('changed source fingerprint rejects reuse',
            lambda: rejected(fixture(), {'source':'changed'}))

        def altered_report():
            data = fixture()
            report.write_text('{"results":[]}', encoding='utf-8')
            rejected(data)
        check('changed suite report rejects reuse', altered_report)

        def altered_log():
            data = fixture()
            log.write_text('PASS everything', encoding='utf-8')
            rejected(data)
        check('changed suite log rejects reuse', altered_log)

        def altered_outcome():
            data = fixture()
            data['results'][0]['passed'] = True
            rejected(data)
        check('failure cannot be waived in the summary', altered_outcome)

        def altered_command():
            data = fixture()
            data['results'][0]['command'].extend(['--opt', '0'])
            rejected(data)
        check('changed suite arguments reject reuse', altered_command)

        def missing_suite():
            data = fixture()
            data['results'] = []
            rejected(data)
        check('incomplete suite queue rejects reuse', missing_suite)

        def changed_during_run():
            data = fixture()
            data['inputs_unchanged'] = False
            rejected(data)
        check('unstable dynamic run rejects reuse', changed_during_run)

        def different_modes():
            data = fixture()
            data['modes'] = ['dynamic', 'frozen']
            rejected(data)
        check('only a standalone dynamic run can be reused', different_modes)

        def missing_artifact():
            data = fixture()
            report.unlink()
            rejected(data)
        check('missing evidence rejects reuse', missing_artifact)
    passed = sum(row['passed'] for row in checks)
    output = ROOT/'target/c11-full-support-guard.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(passed=passed, total=len(checks), results=checks), indent=2)+'\n', encoding='utf-8')
    print(f'{passed}/{len(checks)} C11 gate guard checks passed', flush=True)
    return int(passed != len(checks))


if __name__ == '__main__':
    raise SystemExit(main())
