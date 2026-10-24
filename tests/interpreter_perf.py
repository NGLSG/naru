"""Serial, isolated eval measurements for large additive rule groups.

No source language, MLIR passes or generated executable is involved. Process
startup and STX loading are included and measured separately by load_only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
from native_process import execute

ROOT = Path(__file__).resolve().parents[1]


def rules(count: int) -> str:
    text = ['mod interpreter_perf;',
            'effect[fallback] facts($node) => -1;',
            'effect facts($node) when eq(term.kind($node),1) => 0;']
    text.extend(f'effect facts(Case{i:05d}($value)) => add($value,1);' for i in range(count))
    text.extend([
        'effect run($count,$tag) => bind([$index,$limit,$name,$sum],',
        '    rule.iterate("interpreter_perf.step",[0,$count,$tag,0],1000000),$sum);',
        'effect step([$index,$count,$tag,$sum]) => choose(lt($index,$count),',
        '    [1,[add($index,1),$count,$tag,add($sum,list.head(collect("interpreter_perf.facts",[term($tag,[$index])])))]],',
        '    [0,[$index,$count,$tag,$sum]]);'])
    return '\n'.join(text)+'\n'


def fingerprint(binary: Path) -> dict:
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (binary, binary.with_name('naru_mlir_backend.dll'))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--rules-count', type=int, nargs='+', default=[64,256,1024])
    parser.add_argument('--iterations', type=int, default=2000)
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--report', type=Path, default=ROOT/'target/interpreter-performance.json')
    args = parser.parse_args()
    if not 1 <= args.repeat <= 20 or not 1 <= args.iterations <= 100000:
        parser.error('repeat must be 1..20 and iterations must be 1..100000')
    if any(not 1 <= count <= 10000 for count in args.rules_count):
        parser.error('rules-count must be 1..10000')
    binaries = {'current': args.compiler.resolve()}
    if args.baseline:
        binaries = {'baseline': args.baseline.resolve(), **binaries}
    fingerprints = {name: fingerprint(path) for name,path in binaries.items()}
    if args.baseline:
        assert list(fingerprints['current'].values())[1] == list(fingerprints['baseline'].values())[1], 'Use identical backend DLLs'
    results = []
    with tempfile.TemporaryDirectory(prefix='naru interpreter perf ') as directory:
        work = Path(directory)
        for count in args.rules_count:
            path = work/'rules.stx'
            path.write_text(rules(count), encoding='utf-8')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            tag = f'interpreter_perf.Case{count-1:05d}'
            for name,expression,expected in [('load_only','0','0'),
                    ('collect',f'interpreter_perf.run({args.iterations},"{tag}")',str(args.iterations*(args.iterations+1)//2))]:
                record = {'name':name,'fixed_shape_rules':count,'iterations':args.iterations if name=='collect' else 0,
                          'expression':expression,'expected':expected,'rule_sha256':digest,'samples':[]}
                for iteration in range(args.repeat):
                    order = list(binaries) if iteration % 2 == 0 else list(reversed(binaries))
                    for label in order:
                        sample = {'compiler':label,'passed':False}
                        try:
                            run = execute([str(binaries[label]),'eval','--rules',str(path),'--expr',expression,
                                '--rule-budget','100000000'],cwd=work,env=dict(os.environ,PATH=''),timeout=60,memory_limit=512*1024**2)
                            sample.update(seconds=run.elapsed_seconds,peak_commit_bytes=run.peak_memory_bytes)
                            assert run.returncode==0 and run.stdout.strip()==expected,run.stdout+run.stderr
                            sample['passed']=True
                        except (AssertionError,OSError,subprocess.TimeoutExpired) as error:
                            sample['error']=str(error)[-3000:]
                        record['samples'].append(sample)
                for label in binaries:
                    samples=[s for s in record['samples'] if s['compiler']==label]
                    record[label]={'passed':all(s['passed'] for s in samples)}
                    if record[label]['passed']:
                        record[label].update(median_seconds=statistics.median(s['seconds'] for s in samples),
                                             peak_commit_bytes=max(s['peak_commit_bytes'] for s in samples))
                assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Rules changed during measurement'
                results.append(record)
                print(f"{name} / {count} rules: "+json.dumps({label:record[label] for label in binaries}),flush=True)
    unchanged = fingerprints=={name:fingerprint(path) for name,path in binaries.items()}
    passed = unchanged and all(sample['passed'] for row in results for sample in row['samples'])
    report={'kind':'rule_interpreter_eval','passed':passed,'process_limit':1,'memory_limit_mib':512,
            'repeat':args.repeat,'inputs_unchanged':unchanged,'binaries':fingerprints,'results':results}
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
