# C11 原子对齐与锁自由查询

`c11.atomics.access` 为 load、store、exchange、CAS 和 RMW 选择同一协议：1 字节访问直接使用原生指令；2、4、8 字节检查地址对齐后使用原生指令；其他情况使用 COMDAT 支持锁。

原生指令只声明已检查的大小对齐。锁内访问、atomic_init 和 CAS expected 使用 alignment=1，并保留 volatile。地址、右操作数和内存序在分派前求值一次。浮点重试沿用 [fenv 策略](c11-fenv.md)，锁路径计算一次。

同一对象的访问必须协调，见 [LLVM 原子并发指南](https://llvm.org/docs/Atomics.html)。支持锁的作用域及外部 ABI 限制见 [原子操作](c11-atomics.md)。

## 查询

标准 `atomic_is_lock_free` 按 [WG14 DR 465](https://www.open-std.org/jtc1/sc22/wg14/issues/c11c17/issue0465.html) 采用类型判定，同一原子类型结果一致，接受对应类型的空指针。目标扩展 `__c11_atomic_is_lock_free_address(pointer)` 另行查询实际地址。

规则核对资源头来源及原宏体后，将标准查询绑定到类型检查入口。指针参数求值一次，但不读取所指对象。项目宏、用户宏及后续重定义不受修改。

atomic_flag 的检查保留名义类型，通过 `c11.sema.binding_facts` 存入不透明键。局部遮蔽不会擦除该事实，布局相同的普通结构体也不会被当作 atomic_flag。

## 共享地址分派

`memory_paths` 接受指针宽度、对齐、结果类型、两条回调及参数，生成对齐条件和 SCF 分支，支持零个或多个结果。C 原子协议由调用方提供。

## 测试与限制

```powershell
python tests/c11_atomic_alignment.py
python tests/c11_abi_interop.py
```

packed 用例强制 Naru 使用未对齐地址，Clang 对照使用已记录的自然对齐对象，比较操作结果。外部未对齐 helper 与 Naru 支持锁的互通、跨 DLL 锁共享及全部内存序仍需独立验证。
