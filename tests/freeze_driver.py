"""Build success/failure must remain independent from optional memory sampling."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('naru_freeze_build', ROOT/'tools/freeze/build.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


def main():
    results = []
    def check(name, action):
        try:
            action()
            results.append({'name': name, 'passed': True})
            print('PASS '+name)
        except AssertionError as error:
            results.append({'name': name, 'passed': False, 'error': str(error)})
            print('FAIL '+name+': '+str(error))
    def low_memory():
        error = OSError('simulated process snapshot allocation failure')
        error.winerror = 1455
        raise error
    def success():
        with patch.object(driver, 'process_tree_commit', side_effect=lambda pid: low_memory()):
            metrics = driver.execute([sys.executable, '-c', 'import time; time.sleep(0.4)'], ROOT)
        assert metrics['memory_sample_failure_count'] > 0, metrics
        assert metrics['memory_sample_error_codes'] == [1455], metrics
        assert metrics['peak_sampled_tree_private_commit_bytes'] is None, metrics
    def failure():
        with patch.object(driver, 'process_tree_commit', side_effect=lambda pid: low_memory()):
            try:
                driver.execute([sys.executable, '-c', 'import time; time.sleep(0.4); raise SystemExit(3)'], ROOT)
            except subprocess.CalledProcessError as error:
                assert error.returncode == 3, error
            else:
                raise AssertionError('a real compiler failure was swallowed')
    def jobs():
        result = subprocess.run([sys.executable, str(ROOT/'tools/freeze/build.py'), '--core', 'unused',
            '--rules', 'unused', '--output', 'unused', '--jobs', '0'], capture_output=True, text=True)
        assert result.returncode == 2 and '--jobs must be between' in result.stderr, result.stderr
    check('sampling failure preserves a successful child exit and marks the gap', success)
    check('sampling failure cannot hide an unsuccessful child exit', failure)
    check('invalid worker limits fail before staging or invoking the SDK', jobs)
    passed = sum(item['passed'] for item in results)
    (ROOT/'target/freeze-driver.json').write_text(json.dumps({'passed': passed, 'total': len(results), 'results': results}, indent=2)+'\n')
    print(f'{passed}/{len(results)} freeze driver checks passed')
    return int(passed != len(results))


if __name__ == '__main__':
    raise SystemExit(main())
