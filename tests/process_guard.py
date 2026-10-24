"""Concurrent Windows Job isolation, exact output and child-process denial."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
from native_process import execute

ROOT=Path(__file__).resolve().parents[1]
# A uv virtualenv executable can be a trampoline that starts another process.
# Launch the actual interpreter so this fixture itself obeys the one-process Job.
PYTHON=str(Path(getattr(sys,'_base_executable',sys.executable)).resolve())
ENV=dict(os.environ,PATH='')

def streams(index: int) -> None:
    code=('import sys,time; time.sleep('+str((index%4)*0.01)+'); '
          'print("out-'+str(index)+'"); print("err-'+str(index)+'",file=sys.stderr)')
    result=execute([PYTHON,'-c',code],cwd=ROOT,env=ENV,timeout=5,memory_limit=64*1024**2)
    assert result.returncode==0 and result.stdout=='out-'+str(index)+'\n' and result.stderr=='err-'+str(index)+'\n',str(result)

with ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(streams,range(32)))
print('PASS 32 overlapping process streams remain isolated and removable')
code='''import subprocess,sys
try:
    subprocess.run([sys.executable,"-c","print('unexpected child')"],check=True)
except OSError:
    sys.exit(42)
sys.exit(1)
'''
result=execute([PYTHON,'-c',code],cwd=ROOT,env=ENV,timeout=5)
assert result.returncode==42 and result.stdout=='',str(result)
print('PASS child creation remains forbidden in the Job')
try:
    execute([PYTHON,'-c','import time; time.sleep(20)'],cwd=ROOT,env=ENV,timeout=0.05)
except subprocess.TimeoutExpired:
    pass
else:
    raise AssertionError('Guarded timeout did not stop its own Job')
streams(42)
print('PASS timeout cleanup permits the next guarded invocation')
print('34/34 process guard checks passed')
