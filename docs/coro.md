# MLIR 协程规则库

项目选择 `std/coro` 即可使用同步生成器、异步任务、异步生成器和 promise。语法、类型检查、await 改写和清理来自 STX；core 不包含 async/yield 关键字或协程状态机。

## 同步生成器

```naru
coro fn count(limit:i32)->i32 {
    for i in 0 .. limit { yield i * 7; }
}
fn main()->i32 {
    let g=count(4);
    var total=0;
    while resume(g) { total=total+current(g); }
    destroy(g);
    return total;
}
```

调用创建尚未进入函数体的 `generator<T>`。resume 在调用线程执行到 yield 或完成，返回是否产出值；只有成功产出后可以 current。`yield;` 支持 void。`return;` 或函数末尾结束，随后 resume 返回 false。destroy 释放未启动、暂停或已完成的帧，并执行暂停点已经注册的 defer。

## 异步任务

```naru
async fn compute(n:i32)->i32 {
    await sleep(1);
    return n * 2;
}
async fn answer()->i32 {
    let child=own(compute(21));
    return await move child;
}
fn main()->i32 {
    let job=spawn(answer());
    let n=block_on(job);
    destroy(job);
    return n;
}
```

async fn 返回惰性 `task<T>`；spawn 或 await 启动它。异步函数中的 await 保存执行状态并退出恢复函数，等待完成后由工作线程恢复。普通函数中的 await/block_on 等待结果；工作线程在普通辅助函数中 block_on 时协助执行队列，避免工作线程全部阻塞等待队列内任务。

`suspend;` 主动让出执行机会。sleep(i64) 使用统一计时器队列，不为每个定时器创建线程，不占用工作线程等待；毫秒数必须非负且在时钟范围内。执行器使用 2–4 个工作线程及一个计时器线程。

整数、浮点、bool、void、记录、product、数组、闭包、C 指针和各类协程句柄都有载荷策略；支持 task<task<T>> 等嵌套类型。普通参数、泛型特化、函数值和 async 捕获闭包可以组合。跨模块调用使用公开函数 ABI，内部协程体为私有函数；generator、task、promise、async_generator 在 extern C 边界表示为不透明指针。返回的普通句柄仍需调用者管理，销毁外层任务不会替调用者销毁已取出的句柄。

## 完成、失败、取消和清理

`done(t)` 包括成功、失败、取消；failed/cancelled 区分状态，error 返回 i64，steps 返回恢复/取消步骤数。`fail(code);` 向等待它的异步任务传播失败。普通函数 await 失败任务会 abort；要观察失败，应先等待 done，再检查 failed/error。

| 错误码 | 含义 |
| --- | --- |
| -1 | 取消 |
| -2 | await 依赖成环 |
| -3 | 异步生成器已有未完成的 next |

cancel 是协作式取消，不能抢占正在执行的函数体，到下一次暂停/完成边界处理。destroy 等待正在运行的恢复结束，再释放帧。等待或销毁自己的活动帧属于协议错误，会 abort。

正常完成、fail、取消和提前 destroy 都按后进先出顺序执行已经注册的 defer；尚未执行到的 defer 不会被注册。执行器退出时保持工作线程运行，取消并排空任务；退出清理中新建的任务、定时器、promise 和异步生成器也自动取消。退出清理不能依赖新建异步工作成功完成，需等待的工作应在 main 返回前完成。

## 所有权与句柄

普通句柄是显式资源。复制句柄得到同一对象的别名，destroy 后不能继续调用这些别名；future 不增加独立资源。已注册的 await 持有完成状态和载荷的 pin，即使 owner 同时 destroy，也能安全取得取消事实。

`own(task)` 配合 `await move owner` 表达消费式等待：移动一次，成功、失败、取消都会清理任务；普通函数同样释放消费的任务。再次移动同一 owner 会报错。`defer destroy(move owner)` 可用于只需销毁的资源。

直接 await 新建任务、sleep、next 或已知 async 闭包调用会生成临时清理；`await spawn(existing)` 和返回已有句柄的普通函数不会误销毁调用者资源。

跨暂停的活跃借用、没有生命周期契约的借用参数会被拒绝；借用载荷、移动专属载荷需要额外存储/生命周期规则。普通指针句柄仍由调用者遵守别名有效期。

## Promise 与外部事件

```naru
async fn complete(p:promise<i32>)->void {
    await sleep(1);
    resolve(p,42);
    return;
}
fn main()->i32 {
    let p=promise<i32>();
    let producer=spawn(complete(p));
    let n=await future(p);
    await producer;
    destroy(producer);
    destroy(p);
    return n;
}
```

resolve(p,value)、void 的 resolve(p)、reject(p,code) 返回 bool。完成为单次赋值；重复完成或取消后完成返回 false。`runtime/coro/tasks.h` 提供线程安全 C 接口 naru_task_resolve/reject，可由宿主 I/O 回调完成 promise。外部提供者必须保留 producer 句柄直到所有回调停止使用它；不能在 destroy 后拿旧指针回调。验收包含真实外部线程完成 promise。

`tasks.element(Type)` 与 `tasks.awaitable(CheckedValue)` 是开放等待协议，扩展方言可将自己的受检类型转成 task ABI。含 await 的自定义语句需提供 tasks.body 遍历契约。分配事实由 tasks.fresh 扩展，不能仅根据返回 task 类型猜测所有权。

Promise 用于桥接外部事件。文件、网络、IOCP 等异步 I/O 库尚未提供，fail 使用任务错误码。

## 异步生成器

```naru
async coro fn values()->i32 {
    await sleep(1);
    yield 20;
    await sleep(1);
    yield 22;
}
async fn sum()->i32 {
    let g=values();
    defer destroy(g);
    var n=0;
    while await next(g) { n=n+current(g); }
    return n;
}
fn main()->i32 { return await sum(); }
```

next 返回 `task<bool>`：true 表示一次 yield，false 表示完成；失败/取消传播到请求。同一生成器只允许一个未完成的 next，重复请求失败并保留原请求。取消 next 只取消该请求；cancel(g) 取消生成器。current 在产出后复制载荷，运行中访问会 abort。await、分支、循环、泛型参数与 defer 均可组合。

## 后端与工程

规则位于 coro.stx、tasks.stx、streams.stx。生成上游 MLIR async 方言的 `async.coro.id/begin/save/suspend/free/end`，convert-async-to-llvm 产生 LLVM intrinsics，LLVM 负责帧布局和 resume/destroy 函数分拆。参见 [MLIR Async 方言](https://mlir.llvm.org/docs/Dialects/AsyncDialect/) 和 [LLVM 协程](https://llvm.org/docs/Coroutines.html)。

func.func 带 `llvm.passthrough=["presplitcoroutine"]`。完成事实保存在数据块和任务控制块，完成后帧保留到 destroy，此协议不依赖 LLVM final-suspend/done。同步生成器直接使用 LLVM resume/destroy，异步执行器调用同样入口。tasks.cpp 处理队列、定时器、依赖、完成和释放，不解释 AST 或手写状态机。

Windows/MSVC 工程配置：

```toml
[backend]
target = "exe"
pass_plugins = ["../../target/naru_coro_plugin.dll"]
lowering_pipeline = "builtin.module(convert-scf-to-cf,convert-async-to-llvm,naru-coro-msvc-allocation,convert-to-llvm,reconcile-unrealized-casts)"
[link]
runtime = "crt-static"
libraries = ["../../target/naru_tasks.lib"]
```

目标 pass 将上游帧 aligned_alloc/free 配对转换为 _aligned_malloc/_aligned_free，保留独立分配策略。其他目标可选择自己的管线。当前运行时目标为 Windows x86_64/MSVC。

```powershell
& runtime/coro/build.ps1
.\target\naru.exe build --project examples/async --locked
python tests/coro.py
python tests/tasks.py
python tests/coro_abi.py
.\test.ps1 -CoroAot -Jobs 4
```

生成、MLIR 转换、优化和链接均在 Naru 进程内。验收使用普通源代码、空 PATH，禁止编译器创建子进程，对 O0/O2 分别执行。AOT 验收冻结同一规则组，检查规则/编译器/后端指纹，再执行同一套程序；新 AOT 编译器构建使用安装的 Vyx SDK。
