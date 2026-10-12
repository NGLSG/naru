"""Shared rule-library layout and iterative tree/CFG tools, dynamic or frozen."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import tempfile
from native_process import execute

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler',type=Path,default=ROOT/'target/naru.exe')
    p.add_argument('--frozen',action='store_true')
    a=p.parse_args();results=[]
    rules=[] if a.frozen else [value for path in ('tests/fixtures/rule_tools.stx','dialects/tree.stx','dialects/layout.stx','dialects/cfg.stx','dialects/base.stx') for value in ('--rules',str(ROOT/path))]
    cases=[
        ('sequential layout preserves padding and final alignment','layout.sequential([[1,1],[8,8],[3,1]])','layout.Object(24,8,[0,8,16])',0),
        ('overlap uses maximum extent and common alignment','layout.overlap([[8,8],[13,1],[4,4]])','layout.Object(16,8,[0,0,0])',0),
        ('zero size members preserve their alignment','layout.sequential([[9,1],[0,8]])','layout.Object(16,8,[0,16])',0),
        ('empty object layout','layout.sequential([])','layout.Object(0,1,[])',0),
        ('non power of two target alignment','layout.sequential([[2,3],[7,5]])','layout.Object(15,15,[0,5])',0),
        ('invalid member alignment is rejected','layout.overlap([[4,0]])','invalid object size or alignment',1),
        ('negative extent is rejected','layout.sequential([[-1,1]])','invalid object size or alignment',1),
        ('fold visits constructors lists and leaves','rule_tools.walk(term("outer",[term("inner",[1,2]),[3,4]]))','7',0),
        ('fold preserves preorder across nested constructors','rule_tools.record(term("a",[term("b",[]),[term("c",[])]]))','["a","b","c"]',0),
        ('wide syntax has no per element recursive rule stack','rule_tools.wide(10000)','10001',0),
        ('deep syntax uses an explicit worklist','rule_tools.deep(2048)','2049',0),
        ('scope boundary is chosen by the caller','rule_tools.scoped(rule_tools.Nested([1,rule_tools.Boundary([2,3])]))','4',0),
        ('opaque environments are traversal leaves','rule_tools.walk(env.put(env.empty(),"key",[1,2]))','1',0),
        ('child views preserve constructor order','term.children(term("wide",[1,[2],3]))','[1,[2],3]',0),
        ('child views reject opaque environments','term.children(env.empty())','requires a constructor or list',1),
        ('rebuilding retains original source location','bind($node,term("original",[1]),eq(source.location($node),source.location(term.rebuild($node,[2]))))','1',0),
        ('postorder rewrite preserves unknown tags and list semantics','rule_tools.rewritten(term("unknown",[1,[2,3]]))','unknown(2,[3,4])',0),
        ('postorder rewrite handles deep syntax without recursive stack','rule_tools.rewritten_deep(4096)','4097',0),
        ('wide constructor rewrite uses sequential child views','rule_tools.rewritten_wide(10000)','10000',0),
        ('rewrite prunes and restores parent context with ordered state','rule_tools.scoped_rewrite(rule_tools.Nested([1,rule_tools.Boundary([2]),3]))','[rule_tools.Nested([3,tree.Pruned(),5]),[0,1,3,99,1]]',0),
        ('CFG reachability retains a label after an abrupt path','rule_tools.labels(cfg.Detached(cfg.Jump(1),cfg.Label(1,base.End())))','1',0),
        ('CFG reachability ignores ordinary bodies','rule_tools.labels(base.End())','0',0),
    ]
    with tempfile.TemporaryDirectory(prefix='naru rule tools ') as directory:
        for name,expression,expected,code in cases:
            item={'name':name,'passed':False}
            try:
                r=execute([str(a.compiler.resolve()),'eval',*rules,'--expr',expression,'--rule-budget','100000000'],
                    cwd=directory,env=dict(os.environ,PATH=''),timeout=60,memory_limit=2*1024**3)
                assert r.returncode==code,r.stdout+r.stderr
                assert (expected in r.stdout+r.stderr if code else r.stdout.strip().replace(' ','')==expected.replace(' ','')),r.stdout+r.stderr
                item.update(passed=True,seconds=r.elapsed_seconds,peak_commit_bytes=r.peak_memory_bytes)
            except (AssertionError,OSError) as e:item['error']=str(e)
            results.append(item)
            print(('PASS ' if item['passed'] else 'FAIL ')+name+('' if item['passed'] else ': '+item['error']),flush=True)
    passed=sum(r['passed'] for r in results)
    report=ROOT/'target'/('rule-tools-frozen.json' if a.frozen else 'rule-tools.json')
    report.write_text(json.dumps({'passed':passed,'total':len(results),'results':results},indent=2)+'\n')
    print(f'{passed}/{len(results)} shared rule tool checks passed')
    return int(passed!=len(results))

if __name__=='__main__':raise SystemExit(main())
