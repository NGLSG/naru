"""Additive indexed collection preserves ordering, guards and fallback facts."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen',action='store_true')
    args=parser.parse_args()
    rules=[] if args.frozen else ['--rules',str(ROOT/'tests/fixtures/collect_contract.stx')]
    cases=[
        ('fixed peers retain order','collect("collect_contract.facts",[collect_contract.A(7),0])','[collect_contract.First(7,0),collect_contract.Second(7)]',0),
        ('generic and fixed peers retain order','collect("collect_contract.facts",[collect_contract.A(7),42])','[collect_contract.First(7,42),collect_contract.Generic()]',0),
        ('other fixed head excludes unrelated facts','collect("collect_contract.facts",[collect_contract.B(7),0])','[collect_contract.Other(7)]',0),
        ('wrong constructor arity permits fallback','collect("collect_contract.facts",[collect_contract.A(7,8),0])','[collect_contract.Early()]',0),
        ('fallback peers are additive','collect("collect_contract.defaults",[collect_contract.A(7)])','[collect_contract.Early(),collect_contract.Late()]',0),
        ('false fixed guard permits fallback','collect("collect_contract.guarded",[collect_contract.A(7)])','["fallback"]',0),
        ('unknown head permits generic fallback','collect("collect_contract.facts",[term("unknown",[]),0])','[collect_contract.Early()]',0),
        ('repeated binder matches full arguments','collect("collect_contract.equal",[collect_contract.A(7),7])','[1]',0),
        ('repeated binder mismatch permits fallback','collect("collect_contract.equal",[collect_contract.A(7),8])','[0]',0),
        ('integer head','collect("collect_contract.atom",[42])','["integer"]',0),
        ('string head','collect("collect_contract.atom",["42"])','["string"]',0),
        ('list head','collect("collect_contract.atom",[[42]])','["list"]',0),
        ('zero arguments','collect("collect_contract.arity",[])','[42]',0),
        ('missing arity has no facts','collect("collect_contract.arity",[1,2])','[]',0),
        ('ordinary overlapping peers remain errors','collect_contract.facts(collect_contract.A(7),0)','ambiguous effect',1),
    ]
    results=[]
    with tempfile.TemporaryDirectory(prefix='naru collect ') as directory:
        for name,expression,expected,code in cases:
            row={'name':name,'passed':False}
            try:
                result=execute([str(args.compiler.resolve()),'eval',*rules,'--expr',expression],
                    cwd=directory,env=dict(os.environ,PATH=''),timeout=10,memory_limit=128*1024**2)
                assert result.returncode==code,result.stdout+result.stderr
                assert (expected in result.stdout+result.stderr if code else result.stdout.strip().replace(' ','')==expected),result.stdout+result.stderr
                row['passed']=True
            except (AssertionError,OSError,subprocess.TimeoutExpired) as error:row['error']=str(error)
            results.append(row)
            print(('PASS ' if row['passed'] else 'FAIL ')+name,flush=True)
    report=ROOT/'target'/('collect-frozen.json' if args.frozen else 'collect.json')
    passed=sum(row['passed'] for row in results)
    report.write_text(json.dumps({'passed':passed,'total':len(results),'results':results},indent=2)+'\n')
    print(f'{passed}/{len(results)} additive collection checks passed')
    return int(passed!=len(results))


if __name__ == '__main__':raise SystemExit(main())
