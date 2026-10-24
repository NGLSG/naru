"""Bounded parallel acceptance suites with separate output logs.

Performance measurements remain serial after the acceptance suites finish.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs',type=int,default=4)
    parser.add_argument('--report',type=Path,default=ROOT/'target/parallel-tests.json')
    parser.add_argument('suites',nargs='+')
    args=parser.parse_args()
    if not 1 <= args.jobs <= 64:parser.error('--jobs must be 1..64')
    if len(set(args.suites))!=len(args.suites):parser.error('A suite may only run once')
    paths=[(ROOT/name).resolve() for name in args.suites]
    if any(not path.is_file() or not path.is_relative_to(ROOT) for path in paths):
        parser.error('Suites must be files inside the workspace')
    log_directory=ROOT/'target/test-logs'/uuid.uuid4().hex
    log_directory.mkdir(parents=True)
    def run(index: int, name: str) -> dict:
        log=log_directory/f'{index:02d}-{Path(name).stem}.log'
        print(f'START {name}',flush=True)
        start=time.perf_counter()
        with log.open('w',encoding='utf-8') as stream:
            process=subprocess.run([sys.executable,'-u',str(paths[index])],cwd=ROOT,
                stdout=stream,stderr=subprocess.STDOUT)
        return {'suite':name,'exit':process.returncode,'passed':process.returncode==0,
                'seconds':time.perf_counter()-start,'log':str(log)}
    results={}
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        pending={executor.submit(run,index,name):index for index,name in enumerate(args.suites)}
        for future in as_completed(pending):
            index=pending[future]
            try:row=future.result()
            except OSError as error:row={'suite':args.suites[index],'passed':False,'error':str(error)}
            results[index]=row
            print(('PASS ' if row['passed'] else 'FAIL ')+row['suite'],flush=True)
            if not row['passed'] and 'log' in row:
                print(Path(row['log']).read_text(encoding='utf-8',errors='replace')[-8000:],flush=True)
    ordered=[results[index] for index in range(len(args.suites))]
    passed=sum(row['passed'] for row in ordered)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps({'jobs':args.jobs,'passed':passed,'total':len(ordered),'results':ordered},indent=2)+'\n')
    print(f'{passed}/{len(ordered)} suites passed with at most {args.jobs} concurrent suites',flush=True)
    return int(passed!=len(ordered))


if __name__ == '__main__':raise SystemExit(main())
