# C11 原子操作

`c11.atomics` 实现原子类型、访问及内存序，入口为 `dialects/c11/atomics.stx`。系统头选择和可取地址函数见 [库接口契约](c11-library-contract.md)。

## 类型

`_Atomic(T)` 与 `_Atomic` 限定符分别检查 C11 6.7.2.4 和 6.7.3 的约束。原子身份参与指针类型兼容，左值转换通过 `c11.sema.value_type` 去除原子限定。

支持与 const、volatile、restrict、存储类、原子元素数组、对齐成员及 VLA 指针组合。数组本身和位域不能是原子类型。

## 访问路径

Windows x64 将完整的 1、2、4、8 字节对象映射为整数镜像，浮点和指针通过 `storage` 保留位表示。满足地址对齐要求时，加载和存储生成 LLVM atomic 操作，交换生成 atomicrmw，算术更新使用 cmpxchg 重试。左值地址与右操作数只求值一次。

较大、非二次幂或未对齐的对象使用 COMDAT 支持锁。同一链接映像中的 Naru 翻译单元共享锁，不同 DLL 默认不共享。大聚合 CAS 在锁内比较对象字节，失败时将观察值写回 expected。

所有操作共用 [地址分派](c11-atomic-alignment.md)。锁路径与 expected 访问使用 alignment=1；不能对同一对象混用互不协调的普通访问和锁协议。

## 内存序与头接口

普通原子表达式采用顺序一致，consume 提升为 acquire。内存序可在运行时选择，静态非法值报告诊断，动态非法值触发 trap。CAS 检查失败序不强于成功序。

`__c11_atomic_*` 提供初始化、加载、存储、交换、CAS、整数/指针 fetch、fence 和锁自由查询，供 LLVM 原始 `stdatomic.h` 使用。`c11.atomic_api` 发射资源头要求的六个 flag/fence 普通函数，通过 linkonce COMDAT 合并跨单元定义。

能力宏由开放注册关系贡献。`__STDC_NO_ATOMICS__` 在目标原子能力整体验收前保留。

## 测试与限制

```powershell
python tests/c11_atomics.py
python tests/c11_atomic_alignment.py
```

待完成项包括浮点 CAS 的强制失败及异常传播测试、并发与信号栅栏、padding、跨 DLL 共享锁，以及外部编译器 helper ABI。Naru 的支持锁与 libatomic/compiler-rt 的锁协议尚未互通。

浮点重试的环境保存与恢复见 [浮点环境](c11-fenv.md)。规范参考 [N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)、[LLVM 原子模型](https://llvm.org/docs/Atomics.html) 及 [Clang stdatomic.h](https://github.com/llvm/llvm-project/blob/llvmorg-22.1.1/clang/lib/Headers/stdatomic.h)。
