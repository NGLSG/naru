"""Source-level generators through upstream MLIR async.coro and the native CRT."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

from native_process import execute
from frozen_snapshot import validate_frozen

ROOT = Path(__file__).resolve().parents[1]
EXTRA_OPTIONS = []
EXTRA_INPUTS = []
TASK_RUNTIME = False
IR_SOURCE = None
EXPECTED_STDOUT = {'defer on suspended destruction':'BA','nested handle cancellation cleanup':'I'}
PIPELINE = 'builtin.module(convert-scf-to-cf,convert-async-to-llvm,naru-coro-msvc-allocation,convert-to-llvm,reconcile-unrealized-casts)'
PROGRAMS = [
    ('loop yields', (ROOT/'examples/coro/main.nru').read_text(), 42),
    ('initial suspension', 'coro fn f()->i32{yield 42;}fn main()->i32{let g=f();destroy(g);return 42;}', 42),
    ('SSA lives across suspension', 'coro fn f(n:i32)->i32{let x=n*2;yield x;yield x+1;}fn main()->i32{let g=f(10);var s=0;while resume(g){s=s+current(g);}destroy(g);return s+1;}', 42),
    ('empty and repeatedly completed', 'coro fn f()->i32{}fn main()->i32{let g=f();if resume(g){return 1;}if resume(g){return 2;}destroy(g);return 42;}', 42),
    ('early explicit completion', 'coro fn f()->i32{yield 42;return;yield 1;}fn main()->i32{let g=f();var s=0;while resume(g){s=s+current(g);}destroy(g);return s;}', 42),
    ('destroy while suspended', 'coro fn f()->i32{yield 42;yield 1;}fn main()->i32{let g=f();if resume(g){let n=current(g);destroy(g);return n;}destroy(g);return 1;}', 42),
    ('independent interleaved frames', 'coro fn f(n:i32)->i32{yield n;yield n+1;}fn main()->i32{let a=f(10);let b=f(20);var s=0;while resume(a){s=s+current(a);if resume(b){s=s+current(b);}}destroy(a);destroy(b);return s-20;}', 42),
    ('yield inside branch', 'coro fn f(n:i32)->i32{if n>0{yield n;}else{yield 1;}yield 2;}fn main()->i32{let g=f(40);var s=0;while resume(g){s=s+current(g);}destroy(g);return s;}', 42),
    ('range continue and break', 'coro fn f()->i32{for i in 0 .. 10{if i==0{continue;}if i==4{break;}yield i*7;}}fn main()->i32{let g=f();var s=0;while resume(g){s=s+current(g);}destroy(g);return s;}', 42),
    ('floating payload', 'coro fn f()->f64{yield 21.0;yield 21.0;}fn main()->i32{let g=f();var s:f64=0.0;while resume(g){s=s+current(g);}destroy(g);return s as i32;}', 42),
    ('wide integer payload', 'coro fn f()->u128{let n:u128=18446744073709551616u128;yield n+42;yield n;}fn main()->i32{let g=f();var s:u128=0;while resume(g){s=s+current(g);}destroy(g);return (s as u8) as i32;}', 42),
    ('generator parameters and mutable handles', 'coro fn f()->i32{yield 42;}fn pull(g:generator<i32>)->i32{if resume(g){return current(g);}return 1;}fn main()->i32{var g=f();let n=pull(g);destroy(g);g=f();destroy(g);return n;}', 42),
    ('consumer module without coroutine definitions', 'fn pull(g:generator<i32>)->i32{if resume(g){return current(g);}destroy(g);return 0;}fn main()->i32{return 42;}', 42),
    ('nested pull generators', 'coro fn inner()->i32{yield 21;yield 21;}coro fn outer()->i32{let g=inner();while resume(g){yield current(g);}destroy(g);}fn main()->i32{let g=outer();var s=0;while resume(g){s=s+current(g);}destroy(g);return s;}', 42),
    ('void generator', 'coro fn f()->void{yield;yield;}fn main()->i32{let g=f();var n=0;while resume(g){n=n+21;}destroy(g);return n;}', 42),
    ('aggregate payload', 'struct Pair{a:i32;b:i32;}coro fn f()->Pair{yield Pair{a:20,b:22};}fn main()->i32{let g=f();resume(g);let p=current(g);destroy(g);return p.a+p.b;}', 42),
    ('defer on suspended destruction', 'extern "C" {fn putchar(c:i32)->i32;}coro fn f()->i32{defer putchar(65);defer putchar(66);yield 42;}fn main()->i32{let g=f();resume(g);destroy(g);return 42;}', 42),
    ('nested handle cancellation cleanup', 'extern "C" {fn putchar(c:i32)->i32;}coro fn inner()->i32{defer putchar(73);yield 42;}coro fn outer()->i32{let g=inner();defer destroy(g);resume(g);yield current(g);}fn main()->i32{let g=outer();resume(g);destroy(g);return 42;}', 42),
    ('generic generator composition', 'coro fn f<T>(n:T)->T{yield n;}fn main()->i32{let g=f<i32>(42);resume(g);let n=current(g);destroy(g);return n;}',42),
    ('higher order coroutine function', 'coro fn f(n:i32)->i32{yield n;}fn apply(f:fn(i32)->generator<i32>)->i32{let g=f(42);resume(g);let n=current(g);destroy(g);return n;}fn main()->i32{return apply(fn f);}',42),
    ('array payload', 'coro fn f()->array<2,i32>{yield [20,22];}fn main()->i32{let g=f();resume(g);let a=current(g);destroy(g);return a[0]+a[1];}',42),
    ('closure environment across suspension', 'coro fn f()->i32{let n=20;let c=fn [n](v:i32)->i32{return n+v;};yield c(22);}fn main()->i32{let g=f();resume(g);let n=current(g);destroy(g);return n;}',42),
    ('owned generator moves into defer', 'coro fn f()->i32{yield 42;}fn main()->i32{let g=own(f());defer destroy(move g);return 42;}',42),
]
ERRORS = [
    ('yield outside coroutine', 'fn main()->i32{yield 42;return 0;}', 'yield outside a coroutine'),
    ('yield type mismatch', 'coro fn f()->i32{yield true;}fn main()->i32{return 42;}', 'source type mismatch'),
    ('resume requires generator', 'fn main()->i32{resume(42);return 0;}', 'requires a generator'),
    ('current requires generator', 'fn main()->i32{return current(42);}', 'requires a generator'),
    ('destroy requires generator', 'fn main()->i32{destroy(42);return 0;}', 'requires a generator'),
    ('borrowed yield needs lifetime policy', 'coro fn f()->ref<i32>{}fn main()->i32{return 42;}', 'payload storage policy'),
    ('return value rejected', 'coro fn f()->i32{return 42;}fn main()->i32{return 42;}', 'cannot return a value'),
    ('borrowed generator parameter rejected', 'coro fn f(n:ref<i32>)->i32{yield *n;}fn main()->i32{return 42;}', 'borrowed coroutine parameter'),
]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, default=ROOT/'target/naru.exe')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--jobs', type=int, default=1, help='Concurrent independent source executions (1..16)')
    parser.add_argument('--report', type=Path, default=ROOT/'target/coro.json')
    args = parser.parse_args()
    if not 1 <= args.jobs <= 16:
        parser.error('--jobs must be between 1 and 16')
    compiler = args.compiler.resolve()
    plugin = ROOT/'target/naru_coro_plugin.dll'
    if not plugin.exists():
        raise RuntimeError('Build coroutine target pass: backend/native/plugins/build.ps1')
    provenance = validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/coro.stx']) if args.frozen else None
    paths = [Path(__file__), compiler, compiler.parent/'naru_mlir_backend.dll', plugin,
             ROOT/'examples/coro/main.nru', *EXTRA_INPUTS, *sorted((ROOT/'dialects').rglob('*.stx'))]
    fingerprint = lambda: {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = fingerprint()
    environment = dict(os.environ, PATH='')
    rules = [] if args.frozen else ['--rules', str(ROOT/'dialects/coro.stx')]
    common = [*rules, '--unit', 'program', '--relation', 'coro.emit_program', '--pass-plugin', str(plugin),
              '--lowering-pipeline', PIPELINE, '--runtime', 'crt-static', *EXTRA_OPTIONS]
    results = []
    def record(name, callback):
        row = {'name': name, 'passed': False}
        try:
            callback(row)
            row['passed'] = True
        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
            row['error'] = str(error)[:4000]
        results.append(row)
        print(('PASS ' if row['passed'] else 'FAIL ')+name+('' if row['passed'] else ': '+row['error']), flush=True)
    with tempfile.TemporaryDirectory(prefix='naru coro ') as directory:
        work = Path(directory)
        def compile(source, output, *options):
            return execute([str(compiler), 'build', str(source), *common, *options, '-o', str(output)],
                           cwd=work, env=environment, timeout=30, memory_limit=512*1024**2)
        jobs = []
        for index, (name, text, expected) in enumerate(PROGRAMS):
            source = work/f'valid-{index}.nru'
            source.write_text(text+'\n', encoding='utf-8')
            for level in ('0', '2'):
                def run(row, source=source, level=level, expected=expected, name=name):
                    output = source.with_suffix(f'.O{level}.exe')
                    report = output.with_suffix('.json')
                    built = compile(source, output, '--target', 'exe', '--opt-level', level, '--report', str(report))
                    assert built.returncode == 0, built.stdout+built.stderr
                    details = json.loads(report.read_text())
                    assert details['success'] and details['processes_spawned'] == 0, details
                    result = execute([str(output)], cwd=work, env=environment, timeout=5, memory_limit=128*1024**2)
                    expected_stdout = EXPECTED_STDOUT.get(name,'')
                    assert (result.returncode,result.stdout) == (expected,expected_stdout), (result.returncode, result.stdout, result.stderr)
                    row.update(exit_code=result.returncode, compile_seconds=built.elapsed_seconds,
                               peak_commit_bytes=built.peak_memory_bytes, processes_spawned=details['processes_spawned'])
                jobs.append((f'{name} O{level}',run))
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(record,name,callback) for name,callback in jobs]
            for future in futures:
                future.result()
        for index, (name, text, diagnostic) in enumerate(ERRORS):
            def reject(row, index=index, text=text, diagnostic=diagnostic):
                source = work/f'invalid-{index}.nru'
                source.write_text(text+'\n', encoding='utf-8')
                output = source.with_suffix('.exe')
                output.write_bytes(b'previous artifact')
                built = compile(source, output, '--target', 'exe')
                assert built.returncode != 0 and diagnostic in built.stdout+built.stderr, built.stdout+built.stderr
                assert output.read_bytes() == b'previous artifact', 'failed build changed previous artifact'
                row['diagnostic'] = diagnostic
            record(name, reject)
        def inspect(row):
            source = work/'ir.nru'
            source.write_text(IR_SOURCE or PROGRAMS[0][1], encoding='utf-8')
            output = work/'before.mlir'
            built = compile(source, output, '--target', 'mlir', '--opt-level', '0')
            assert built.returncode == 0, built.stdout+built.stderr
            text = output.read_text()
            for operation in ('async.coro.id', 'async.coro.begin', 'async.coro.save', 'async.coro.suspend', 'async.coro.free', 'async.coro.end'):
                assert operation in text, operation
            lowered = work/'after.mlir'
            built = compile(source, lowered, '--target', 'mlir', '--pass-pipeline',
                            'builtin.module(convert-scf-to-cf,convert-async-to-llvm,naru-coro-msvc-allocation)')
            assert built.returncode == 0, built.stdout+built.stderr
            text = lowered.read_text()
            assert 'llvm.call @_aligned_malloc' in text and 'llvm.call @_aligned_free' in text, text
            assert 'llvm.call @aligned_alloc' not in text, text
            assert ('llvm.call @naru_task_destroy' if TASK_RUNTIME else 'llvm.call @free') in text, 'payload ownership must reach its allocator'
            row['lowering_pipeline'] = PIPELINE
        record('upstream coroutine IR and paired CRT allocation', inspect)
        def allocator_policy(row):
            source = work/'allocator.mlir'
            source.write_text('''module {
  llvm.func @_aligned_malloc(i64, i64) -> !llvm.ptr
  llvm.func @_aligned_free(!llvm.ptr)
  llvm.func @malloc(i64) -> !llvm.ptr
  llvm.func @free(!llvm.ptr)
  func.func @upstream() -> !async.coro.handle {
    %id = async.coro.id
    %h = async.coro.begin %id
    async.coro.free %id, %h
    return %h : !async.coro.handle
  }
  llvm.func @ordinary_allocator() -> !llvm.ptr {
    %zero = llvm.mlir.constant(0 : i32) : i32
    %null = llvm.mlir.zero : !llvm.ptr
    %id = llvm.intr.coro.id %zero, %null, %null, %null : (i32, !llvm.ptr, !llvm.ptr, !llvm.ptr) -> token
    %size = llvm.mlir.constant(64 : i64) : i64
    %memory = llvm.call @malloc(%size) : (i64) -> !llvm.ptr
    %h = llvm.intr.coro.begin %id, %memory : (token, !llvm.ptr) -> !llvm.ptr
    %allocation = llvm.intr.coro.free %id, %h : (token, !llvm.ptr) -> !llvm.ptr
    llvm.call @free(%allocation) : (!llvm.ptr) -> ()
    llvm.return %h : !llvm.ptr
  }
}
''', encoding='utf-8')
            output = work/'allocator-after.mlir'
            built = execute([str(compiler), 'opt', str(source), '--target', 'mlir', '--pass-plugin', str(plugin),
                             '--pass-pipeline', 'builtin.module(convert-async-to-llvm,naru-coro-msvc-allocation)', '-o', str(output)],
                            cwd=work, env=environment, timeout=30, memory_limit=512*1024**2)
            assert built.returncode == 0, built.stdout+built.stderr
            text = output.read_text()
            assert text.count('llvm.call @_aligned_malloc') == 1 and text.count('llvm.call @_aligned_free') == 1, text
            assert text.count('llvm.call @malloc') == 1 and text.count('llvm.call @free') == 1, text
            row['preserves_independent_allocator'] = True
        record('target pass preserves independently allocated coroutine frames', allocator_policy)
    unchanged = before == fingerprint()
    if args.frozen:
        unchanged = unchanged and provenance == validate_frozen(compiler, core=ROOT/'target/naru.exe', required_rules=[ROOT/'dialects/coro.stx'])
    passed = sum(row['passed'] for row in results)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'passed': passed, 'total': len(results), 'inputs_unchanged': unchanged,
                                      'frozen_provenance': provenance, 'sha256': before, 'results': results}, indent=2)+'\n', encoding='utf-8')
    print(f'{passed}/{len(results)} coroutine checks; inputs unchanged: {unchanged}')
    return int(passed != len(results) or not unchanged)

if __name__ == '__main__':
    raise SystemExit(main())
