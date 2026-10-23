# C11 系统线程接口

线程类型、互斥量、条件变量、TSS、once_flag 和时间类型来自实际 MSVC `threads.h`，底层函数链接系统运行库。包含路径由工具链发现。

`thrd_t` 等记录的按值传参、返回值和线程入口函数指针复用 `c11.abi`。timedlock、timedwait、sleep 的头内联实现由 Naru 编译。

目标保留字由 `c11.lex.extension_keyword` 定义，例如形参中的 `__restrict`。TLS 由 `c11.thread_storage` 发射原生线程存储，LLVM 全局属性为 `tls_mode = 1`（GeneralDynamic）。库接口 tss_create/tss_get 使用系统实现。

## 测试与限制

```powershell
python tests/c11_threads.py
```

输入包括线程创建、加入、分离、退出、身份、TLS、递归锁、定时等待、条件变量、call_once、TSS 析构、跨单元及原子更新。共享可变数据通过互斥量或原子访问。

浮点原子压力用例通过并发写入制造 CAS 重试机会，但仍需确定性失败注入。硬件陷阱、线程错误路径及完整 7.26 审核尚未完成，`__STDC_NO_THREADS__` 保留至线程能力整体验收。
