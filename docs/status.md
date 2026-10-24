# 实现状态

更新于 2026-10-23，版本 `0.2.0-preview.1`。平台为 Windows x86_64；C11 使用 MSVC/UCRT 的 LLP64 ABI。

## 编译器

已实现动态规则加载、AOT 固化、规则库组合、项目依赖和包管理。MLIR、LLVM 和 LLD 均在进程内运行，支持自定义方言、pass 插件及原生程序分发。

当前核心回归通过 12 组套件。长迭代为 16/16，在 128 MiB 限额内最高约 89 MB；前端基础设施为 93/93，base 函数与控制流为 34/34。

## C11

语言功能及模块见 [C11 方言](c11.md)。最近的条款套件为 310/314，其中两项数组边界诊断已修复并通过定向 O0/O2 复测；完整套件尚未重跑。声明模型为 98/98。

当前已知失败：

- 8,192 元素联合体初始化在 O0/O2 下超过 512 MiB 编译内存限制。
- 真实系统头专项为 42/52，stdio 和四类 stdatomic 用例在同一内存限制下失败。
- `examples/c11` 在当前系统头环境中触发 `c11.sema.conversion` 的布尔转换 fallback 歧义。
- 完整 C11 规则组的最新冻结构建未完成。

标准库使用系统 SDK/CRT 及编译器资源头。全部语言条款、库接口和跨编译器 ABI 的统一验收尚未完成，完整 C11 支持仍在进行中。测试用例通过率不换算为标准覆盖率。

## 其他规则库

B、Pascal、BASIC 的支持范围分别见 [B](b.md)、[Pascal](pascal.md)、[BASIC](basic.md)。[协程库](coro.md) 提供生成器、任务、promise、线程池和定时器；文件及网络异步 I/O 库尚未提供。

普通函数的所有权检查仍缺少部分移动、自动析构和跨函数生命周期推断。其他宿主平台尚未完成构建与运行验证。

## 测试入口

| 内容 | 脚本 |
| --- | --- |
| 语法与规则求值 | `tests/run.py`、`tests/rules.py` |
| 长迭代与临时对象回收 | `tests/iteration.py` |
| C11 条款 | `tests/c11_conformance.py` |
| 声明与系统头 | `tests/c11_declaration_model.py`、`tests/c11_header_features.py` |
| C11 总验收 | `tests/c11_full_support.py` |
| 分发包 | `tests/distribution.py` |

详细测试说明见 [tests/README.md](../tests/README.md)，2026-10-23 的工具链与内存诊断见 [验证记录](vyx-dist-20261023.md)。本地报告保存在 `target/verification/`。
