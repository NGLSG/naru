"""Native async task, scheduler, dependency and cancellation acceptance."""
from pathlib import Path
import sys
import subprocess
import coro

ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT/'target/task_provider.obj'
coro.EXTRA_OPTIONS = ['--link-library', str(ROOT/'target/naru_tasks.lib'), '--link-object', str(PROVIDER),'--rules',str(ROOT/'tests/fixtures/await_wrapper.stx')]
coro.EXTRA_INPUTS = [Path(__file__), ROOT/'runtime/coro/tasks.cpp', ROOT/'runtime/coro/tasks.h', ROOT/'target/naru_tasks.lib', ROOT/'tests/fixtures/task_provider.cpp',ROOT/'tests/fixtures/await_wrapper.stx',PROVIDER]
coro.TASK_RUNTIME = True
coro.PROGRAMS = [
 ('generic async generator with arguments', 'async coro fn f<T>(n:T)->T{await sleep(1);yield n;}fn main()->i32{let g=f<i32>(42);await next(g);let n=current(g);destroy(g);return n;}',42),
 ('generic async generator without arguments', 'async coro fn f<T>()->T{await sleep(1);yield 42;}fn main()->i32{let g=f<i32>();await next(g);let n=current(g);destroy(g);return n;}',42),
 ('nested task payload', 'async fn child()->i32{return 42;}async fn factory()->task<i32>{return child();}fn main()->i32{let t=await factory();let n=await t;destroy(t);if live_tasks()==0{return n;}return 1;}',42),
 ('generator handle payload', 'coro fn f()->i32{yield 42;}async fn factory()->generator<i32>{return f();}fn main()->i32{let g=await factory();resume(g);let n=current(g);destroy(g);return n;}',42),
 ('async generator handle payload', 'async coro fn f()->i32{yield 42;}async fn factory()->async_generator<i32>{return f();}fn main()->i32{let g=await factory();await next(g);let n=current(g);destroy(g);return n;}',42),
 ('promise handle payload', 'async fn factory()->promise<i32>{return promise<i32>();}fn main()->i32{let p=await factory();resolve(p,42);let n=await future(p);destroy(p);return n;}',42),
 ('C pointer payload', 'extern "C" {fn is_null(p:ptr)->i32;}async fn f(p:ptr)->ptr{return p;}fn main()->i32{let p:ptr=null;let q=await f(p);return is_null(q);}',42),
 ('dependency cycle is failure', 'async fn f(p:promise<task<i32>>)->i32{let t=await future(p);return await t;}fn main()->i32{let pa=promise<task<i32>>();let pb=promise<task<i32>>();let a=spawn(f(pa));let b=spawn(f(pb));resolve(pa,b);resolve(pb,a);while !done(a) || !done(b){}let n=error(a);destroy(a);destroy(b);destroy(pa);destroy(pb);if n==-2{return 42;}return 1;}',42),
 ('shutdown cancels tasks created by cleanup', 'async fn leaf()->i32{return 42;}fn cleanup()->void{let t=leaf();let p=promise<i32>();let g=stream();let s=sleep(10000);}async coro fn stream()->i32{yield 1;}async fn p()->i32{defer cleanup();await sleep(10000);return 1;}fn main()->i32{let t=spawn(p());while steps(t)<1{}return 42;}',42),
 ('cancelled next replaced while frame runs', 'extern "C" {fn hold_frame()->i32;fn wait_frame()->i32;fn release_frame()->i32;}async coro fn f()->i32{yield hold_frame();}fn main()->i32{let g=f();let a=next(g);wait_frame();cancel(a);while !done(a){}destroy(a);let b=next(g);release_frame();if await b{let n=current(g);destroy(b);destroy(g);return n;}destroy(b);destroy(g);return 1;}',42),
 ('cancel during running yield reaches cleanup', 'extern "C" {fn hold_frame()->i32;fn wait_frame()->i32;fn release_frame()->i32;fn putchar(c:i32)->i32;}async coro fn f()->i32{defer putchar(71);yield hold_frame();}fn main()->i32{let g=f();let a=next(g);wait_frame();cancel(g);release_frame();while !done(g){}var n=1;if cancelled(g){n=42;}destroy(a);destroy(g);return n;}',42),
 ('async closure temporaries are released', 'fn main()->i32{let f=async fn []()->i32{return 1;};var n=0;while n<12{n=n+await f();}if live_tasks()==0{return 42;}return live_tasks() as i32;}',42),
 ('nested array await retains explicit type', 'async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);let a:array<2,array<2,u8>>=[[20,2],[await t,0]];return (a[0][0] as i32)+(a[0][1] as i32)+(a[1][0] as i32);}fn main()->i32{return await p();}',42),
 ('nested array assignment retains expected type', 'async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);var a:array<2,array<2,u8>>=[[0,0],[0,0]];a=[[20,2],[await t,0]];return (a[0][0] as i32)+(a[0][1] as i32)+(a[1][0] as i32);}fn main()->i32{return await p();}',42),
 ('nested array store retains expected type', 'async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);var a:array<1,array<2,array<2,u8>>>=[[[0,0],[0,0]]];a[0]=[[20,2],[await t,0]];return (a[0][0][0] as i32)+(a[0][0][1] as i32)+(a[0][1][0] as i32);}fn main()->i32{return await p();}',42),
 ('array return retains expected type across await', 'async fn f()->u8{return 22;}async fn p()->array<2,u8>{return [20,await f()];}fn main()->i32{let a=await p();return (a[0] as i32)+(a[1] as i32);}',42),
 ('array yield retains expected type across await', 'async fn f()->u8{return 22;}async coro fn p()->array<2,u8>{yield [20,await f()];}fn main()->i32{let g=p();await next(g);let a=current(g);destroy(g);return (a[0] as i32)+(a[1] as i32);}',42),
 ('owned blocking await releases consumed task', 'async fn f()->i32{return 42;}fn main()->i32{let t=own(f());let n=await move t;if live_tasks()==0{return n;}return 1;}',42),
 ('owned suspending await releases consumed task', 'async fn f()->i32{await sleep(1);return 42;}async fn p()->i32{let t=own(f());return await move t;}fn main()->i32{let n=await p();if live_tasks()==0{return n;}return 1;}',42),
 ('owned failed await releases consumed task', 'async fn f()->i32{fail(42);}async fn p()->i32{let t=own(f());return await move t;}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);if live_tasks()==0{return n;}return 1;}',42),
 ('owned cancelled await releases consumed task', 'async fn f()->i32{await sleep(10000);return 1;}async fn p()->i32{let t=own(f());return await move t;}fn main()->i32{let t=spawn(p());while steps(t)<1{}cancel(t);while !done(t){}destroy(t);if live_tasks()==0{return 42;}return 1;}',42),
 ('lazy task and await', 'async fn f()->i32{return 42;}fn main()->i32{let t=f();let n=await t;destroy(t);return n;}',42),
 ('suspending parent and child', 'async fn f(n:i32)->i32{suspend;return n*2;}async fn p()->i32{let t=f(20);defer destroy(t);let n=await t;return n+2;}fn main()->i32{let t=spawn(p());let n=block_on(t);destroy(t);return n;}',42),
 ('await operands and calls', 'fn add(a:i32,b:i32)->i32{return a+b;}async fn f()->i32{suspend;return 21;}async fn p()->i32{let a=f();let b=f();defer destroy(a);defer destroy(b);return add(await a,await b);}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('short circuit preserves unexecuted awaits', 'async fn f()->bool{fail(7);}async fn p()->i32{let t=f();defer destroy(t);if false && await t{return 1;}if true || await t{return 42;}return 2;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('await loop condition', 'async fn yes(n:i32)->bool{suspend;return n<3;}async fn p()->i32{var n=0;while await yes(n){n=n+1;}return n*14;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('void completion and await', 'async fn f()->void{suspend;return;}async fn p()->i32{let t=f();await t;destroy(t);return 42;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('record task result', 'struct P{a:i32;b:i32;}async fn f()->P{suspend;return P{a:20,b:22};}fn main()->i32{let t=f();let p=await t;destroy(t);return p.a+p.b;}',42),
 ('completion can be awaited repeatedly', 'async fn f()->i32{return 21;}fn main()->i32{let t=f();let a=await t;let b=await t;destroy(t);return a+b;}',42),
 ('failure state and exact error', 'async fn f()->i32{fail(42);}fn main()->i32{let t=spawn(f());while !done(t){}if failed(t){let n=error(t) as i32;destroy(t);return n;}destroy(t);return 1;}',42),
 ('failure propagates through awaiting parent', 'async fn f()->i32{fail(42);}async fn p()->i32{let t=f();defer destroy(t);return await t;}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('cancel dormant task never enters body', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{putchar(88);return 1;}fn main()->i32{let t=f();cancel(t);while !done(t){}var n=0;if cancelled(t){n=42;}destroy(t);return n;}',42),
 ('normal completion runs defers once', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{defer putchar(65);defer putchar(66);suspend;return 42;}fn main()->i32{let t=f();let n=await t;destroy(t);return n;}',42),
 ('failure runs defers once', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{defer putchar(65);fail(42);}fn main()->i32{let t=spawn(f());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('fair repeated suspension', 'async fn f(n:i32)->i32{var i=0;while i<n{suspend;i=i+1;}return 21;}async fn p()->i32{let a=spawn(f(200));let b=spawn(f(200));defer destroy(a);defer destroy(b);return await a+await b;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('ordinary expression effects occur before later await', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{putchar(66);return 42;}async fn p()->i32{let t=f();defer destroy(t);return putchar(65)-65+await t;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('cancellation runs registered defers', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{defer putchar(65);while true{suspend;}return 1;}fn main()->i32{let t=spawn(f());while steps(t)<1{}cancel(t);while !done(t){}var n=0;if cancelled(t){n=42;}destroy(t);return n;}',42),
 ('cancel parent destroys suspended child', 'extern "C" {fn putchar(c:i32)->i32;}async fn child()->i32{defer putchar(73);while true{suspend;}return 1;}async fn parent()->i32{let c=spawn(child());defer destroy(c);while steps(c)<1{suspend;}return await c;}fn main()->i32{let t=spawn(parent());while steps(t)<1{}cancel(t);while !done(t){}destroy(t);return 42;}',42),
 ('timer awaits do not occupy workers', 'async fn f()->i32{await sleep(1);return 7;}async fn p()->i32{let a=spawn(f());let b=spawn(f());let c=spawn(f());let d=spawn(f());let e=spawn(f());let f1=spawn(f());defer destroy(a);defer destroy(b);defer destroy(c);defer destroy(d);defer destroy(e);defer destroy(f1);return await a+await b+await c+await d+await e+await f1;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('cancel timer dependency', 'async fn f()->i32{await sleep(10000);return 1;}fn main()->i32{let t=spawn(f());while steps(t)<1{}cancel(t);while !done(t){}var n=0;if cancelled(t){n=42;}destroy(t);return n;}',42),
 ('temporary child cleaned on failed await', 'async fn f()->i32{fail(42);}async fn p()->i32{return await f();}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('generic async function', 'async fn f<T>(n:T)->T{suspend;return n;}fn main()->i32{let t=f<i32>(42);let n=await t;destroy(t);return n;}',42),
 ('higher order async function', 'async fn f(n:i32)->i32{suspend;return n;}fn run(f:fn(i32)->task<i32>)->i32{let t=f(42);let n=await t;destroy(t);return n;}fn main()->i32{return run(fn f);}',42),
 ('worker blocking helper assists queue', 'async fn step(n:i32)->i32{if n==0{return 42;}return sync(n-1);}fn sync(n:i32)->i32{let t=step(n);let v=block_on(t);destroy(t);return v;}fn main()->i32{return sync(8);}',42),
 ('recursive suspending awaits', 'async fn f(n:i32)->i32{if n==0{return 42;}return await f(n-1);}fn main()->i32{let t=f(32);let n=await t;destroy(t);return n;}',42),
 ('await spawn preserves existing handle', 'async fn f()->i32{return 21;}async fn p()->i32{let t=f();let n=await spawn(t);let m=await t;destroy(t);return n+m;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('repeat spawn respects pending dependency', 'async fn child()->i32{await sleep(20);return 42;}async fn parent()->i32{let c=child();defer destroy(c);return await c;}fn main()->i32{let t=spawn(parent());while steps(t)<1{}spawn(t);let n=block_on(t);destroy(t);return n;}',42),
 ('array assignment await propagates failure', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{fail(42);}async fn p()->i32{var a=[0];defer putchar(65);a[0]=await f();return a[0];}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('defer argument await precedes registration', 'extern "C" {fn putchar(c:i32)->i32;}async fn f()->i32{fail(42);}async fn p()->i32{defer putchar(66);defer putchar(await f());return 1;}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('record await preserves declared field order', 'extern "C" {fn putchar(c:i32)->i32;}struct R{a:i32;b:i32;}async fn f()->i32{putchar(66);return 22;}async fn p()->i32{let t=f();defer destroy(t);let r=R{b:await t,a:putchar(65)-45};return r.a+r.b;}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('owner destruction keeps await cancellation fact alive', 'async fn c()->i32{await sleep(1000);return 42;}async fn p(t:task<i32>)->i32{return await t;}fn main()->i32{let c=c();let p=spawn(p(c));while steps(p)<1{}destroy(c);while !done(p){}var n=1;if failed(p) && error(p)==-1{n=42;}destroy(p);return n;}',42),
 ('executor shutdown cleans parents and children', 'extern "C" {fn putchar(c:i32)->i32;}async fn c()->i32{await sleep(10000);return 1;}async fn p()->i32{let c=c();defer destroy(c);defer putchar(80);return await c;}fn main()->i32{let t=spawn(p());while steps(t)<1{}return 42;}',42),
 ('fresh blocking await releases each task', 'async fn f()->i32{return 1;}fn main()->i32{var n=0;while n<5000{n=n+block_on(f());}if live_tasks()==0{return 42;}return 1;}',42),
 ('promise completed from another task', 'async fn complete(p:promise<i32>)->void{await sleep(1);resolve(p,42);return;}fn main()->i32{let p=promise<i32>();let producer=spawn(complete(p));let n=await future(p);await producer;destroy(producer);destroy(p);return n;}',42),
 ('promise completion is single assignment', 'fn main()->i32{let p=promise<i32>();resolve(p,42);if resolve(p,1){destroy(p);return 1;}let n=await future(p);destroy(p);return n;}',42),
 ('void promise', 'fn main()->i32{let p=promise<void>();resolve(p);await future(p);destroy(p);return 42;}',42),
 ('rejected promise propagates failure', 'async fn p(t:task<i32>)->i32{return await t;}fn main()->i32{let x=promise<i32>();let t=spawn(p(future(x)));reject(x,42);while !done(t){}let n=error(t) as i32;destroy(t);destroy(x);return n;}',42),
 ('async closure copies its environment into frame', 'fn main()->i32{let n=20;let f=async fn [n](v:i32)->i32{await sleep(1);return n+v;};let t=f(22);let v=await t;destroy(t);return v;}',42),
 ('closure invoked after suspension', 'async fn p()->i32{let n=20;let f=fn [n](v:i32)->i32{return n+v;};await sleep(1);return f(22);}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('external callback resolves typed promise', 'extern "C" {fn complete_promise(p:promise<i32>)->i32;}fn main()->i32{let p=promise<i32>();complete_promise(p);let n=await future(p);destroy(p);return n;}',42),
 ('user awaitable conversion contract', 'async fn f()->i32{return 42;}async fn p()->i32{let t=f();defer destroy(t);return await wrapped(t);}fn main()->i32{let t=p();let n=await wrapped(t);destroy(t);return n;}',42),
 ('async generator awaits and yields on demand', 'async coro fn f()->i32{await sleep(1);yield 20;await sleep(1);yield 22;}async fn sum()->i32{let g=f();defer destroy(g);var n=0;while await next(g){n=n+current(g);}return n;}fn main()->i32{let t=sum();let n=await t;destroy(t);return n;}',42),
 ('async generator failure preserves cleanup', 'extern "C" {fn putchar(c:i32)->i32;}async coro fn f()->i32{defer putchar(71);await sleep(1);fail(42);}async fn p()->i32{let g=f();defer destroy(g);if await next(g){return current(g);}return 1;}fn main()->i32{let t=spawn(p());while !done(t){}let n=error(t) as i32;destroy(t);return n;}',42),
 ('async generator completed requests return false', 'async coro fn f()->i32{}fn main()->i32{let g=f();if await next(g){return 1;}if await next(g){return 2;}destroy(g);return 42;}',42),
 ('contextual array argument retains narrow element type', 'fn add(a:array<2,u8>,b:u8)->i32{return (a[0] as i32)+(a[1] as i32)+(b as i32);}async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);return add([20,2],await t);}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('contextual record field retains narrow array type', 'struct R{a:array<2,u8>;b:u8;}async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);let r=R{a:[20,2],b:await t};return (r.a[0] as i32)+(r.a[1] as i32)+(r.b as i32);}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('indirect call retains argument context across await', 'fn add(a:array<2,u8>,b:u8)->i32{return (a[0] as i32)+(a[1] as i32)+(b as i32);}async fn f()->u8{return 20;}async fn p()->i32{let t=f();defer destroy(t);return (fn add)([20,2],await t);}fn main()->i32{let t=p();let n=await t;destroy(t);return n;}',42),
 ('duplicate next request fails without advancing producer', 'async coro fn f()->i32{await sleep(20);yield 42;}fn main()->i32{let g=f();let a=next(g);let b=next(g);if !failed(b){return 1;}if await a{let n=current(g);destroy(a);destroy(b);destroy(g);return n;}return 2;}',42),
 ('async generator cancel executes capture cleanup', 'extern "C" {fn putchar(c:i32)->i32;}async coro fn f()->i32{defer putchar(71);await sleep(1000);yield 1;}fn main()->i32{let g=f();let n=next(g);while steps(g)<1{}destroy(g);while !done(n){}destroy(n);return 42;}',42),
]
coro.EXPECTED_STDOUT.update({'normal completion runs defers once':'BA','failure runs defers once':'A','ordinary expression effects occur before later await':'AB','cancellation runs registered defers':'A','cancel parent destroys suspended child':'I','array assignment await propagates failure':'A','defer argument await precedes registration':'B','record await preserves declared field order':'AB','executor shutdown cleans parents and children':'P'})
coro.EXPECTED_STDOUT['async generator failure preserves cleanup'] = 'G'
coro.EXPECTED_STDOUT['async generator cancel executes capture cleanup'] = 'G'
coro.EXPECTED_STDOUT['cancel during running yield reaches cleanup'] = 'G'
coro.IR_SOURCE = coro.PROGRAMS[0][1]
coro.ERRORS = [
 ('consumed task cannot be moved again', 'async fn f()->i32{return 42;}fn main()->i32{let t=own(f());let n=await move t;destroy(move t);return n;}', 'move requires a live'),
 ('await requires task', 'fn main()->i32{return await 42;}', 'requires a task'),
 ('promise completion checks payload type', 'fn main()->i32{let p=promise<i32>();resolve(p,true);destroy(p);return 42;}', 'source type mismatch'),
 ('task is not a promise producer', 'async fn f()->i32{return 42;}fn main()->i32{let t=f();resolve(t,1);destroy(t);return 42;}', 'requires a promise'),
 ('pull operations reject async tasks', 'async fn f()->i32{return 42;}fn main()->i32{let t=f();resume(t);destroy(t);return 42;}', 'requires a generator'),
 ('fail requires async function', 'fn main()->i32{fail(42);return 1;}', 'fail outside async fn'),
 ('pause requires async function', 'fn main()->i32{suspend;return 42;}', 'suspend outside async fn'),
 ('task cannot yield', 'async fn f()->i32{yield 42;}fn main()->i32{return 42;}', 'yield outside a coroutine'),
 ('borrow cannot cross suspension', 'async fn f()->i32{let n=own(42);let r=&n;suspend;let v=*r;end r;return v;}fn main()->i32{return 42;}', 'live borrow across coroutine suspension'),
 ('missing task result is rejected', 'async fn f()->i32{suspend;}fn main()->i32{return 42;}', 'finish without a result'),
 ('borrowed parameter requires lifetime contract', 'async fn f(p:ref<i32>)->i32{return *p;}fn main()->i32{return 42;}', 'borrowed coroutine parameter'),
]
if __name__ == '__main__':
    subprocess.run(['clang++','-std=c++20','-O2','-fms-runtime-lib=static','-c',str(ROOT/'tests/fixtures/task_provider.cpp'),'-o',str(PROVIDER)],check=True)
    if '--report' not in sys.argv:
        sys.argv.extend(['--report', str(ROOT/'target/tasks.json')])
    raise SystemExit(coro.main())
