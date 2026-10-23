"""Standard-library logs use stderr and preserve machine-readable stdout."""
from __future__ import annotations
import json
import os
from pathlib import Path
import tempfile
from native_process import execute

ROOT=Path(__file__).resolve().parents[1]


def main() -> int:
    results=[]
    compiler=ROOT/'target/naru.exe'
    rule_args=['--rules',str(ROOT/'tests/fixtures/collect_contract.stx')]
    with tempfile.TemporaryDirectory(prefix='naru CLI logging ') as directory:
        work=Path(directory)
        def check(name,arguments,code,stdout,log=None):
            row={'name':name,'passed':False}
            try:
                run=execute([str(compiler),*arguments],cwd=work,env=dict(os.environ,PATH=''),timeout=15,memory_limit=512*1024**2)
                assert run.returncode==code,run.stdout+run.stderr
                assert run.stdout.strip()==stdout,repr(run.stdout)
                assert (log in run.stderr if log else not run.stderr),repr(run.stderr)
                if code: assert run.stderr.startswith('[error] '),repr(run.stderr)
                row['passed']=True
            except (AssertionError,OSError) as error:row['error']=str(error)
            results.append(row)
            print(('PASS ' if row['passed'] else 'FAIL ')+name+('' if row['passed'] else ': '+row['error']),flush=True)
        for level in (None,'trace','debug','info','warn','error'):
            flags=['--log-level',level] if level else []
            check('eval stdout at '+str(level),['eval',*rule_args,'--expr','add(20,22)',*flags],0,'42',
                  'rule evaluation completed in 3 steps' if level in ('trace','debug') else None)
        check('invalid option diagnostic',['eval',*rule_args,'--unknown','x'],2,'','[error] unknown option')
        check('invalid log level diagnostic',['eval',*rule_args,'--log-level','off'],2,'','[error] invalid log level')
        check('effect mismatch diagnostic',['eval',*rule_args,'--expr','collect_contract.atom(1)'],1,'','no matching effect')
        for level in ('info','error'):
            output=work/(level+'.mlir')
            check('artifact log at '+level,['build',str(ROOT/'examples/answer.nru'),'--rules',str(ROOT/'dialects/base.stx'),
                '--target','mlir','-o',str(output),'--log-level',level],0,'','[info] naru: wrote' if level=='info' else None)
            if results[-1]['passed'] and (not output.is_file() or 'module' not in output.read_text()):
                results[-1].update(passed=False,error='artifact was not produced')
    passed=sum(row['passed'] for row in results)
    (ROOT/'target/cli-logging.json').write_text(json.dumps({'passed':passed,'total':len(results),'results':results},indent=2)+'\n')
    print(f'{passed}/{len(results)} stdout/stderr logging checks passed')
    return int(passed!=len(results))


if __name__ == '__main__':raise SystemExit(main())
