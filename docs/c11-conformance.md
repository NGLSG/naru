# C11 测试与条款审核

检查基准为 [WG14 N1570](https://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf)，目标为 Windows x86_64 LLP64。当前结果见 [实现状态](status.md)，全量工作项见 [支持计划](c11-full-support.md)。

## 清单

| 文件 | 内容 |
| --- | --- |
| `tests/c11/conformance.json` | 条款、功能组、测试输入和剩余工作 |
| `tests/c11/support-plan.json` | 工作项及完成条件 |
| `tests/c11/support-probes.json` | 待完成特性与已知缺陷的探测输入 |
| `tests/c11/projects/sources.json` | 真实项目来源、版本及哈希 |

`partial` 表示部分实现，`missing` 表示缺少能力。测试输入用于检查具体行为；条款状态由完整约束、诊断和实现策略的审核决定。

## 运行

```powershell
python tests/c11_conformance.py --feature constants
python tests/c11_conformance.py
python tests/c11_support.py
python tests/c11_headers.py
python tests/c11_stress.py
```

逐条套件将合法程序与独立 Clang 对照，检查 O0/O2 运行结果。非法程序检查必需诊断和旧产物保护；未定义行为由夹具注明，不要求运行结果与参考编译器一致。

Naru 在 PATH 为空、禁止子进程的 Windows Job 中编译，逐条套件默认限制 512 MiB、30 秒。真实项目和系统头基线各有资源配置，参数见对应脚本。报告记录时间、内存、退出值、诊断和输入哈希；测试期间输入变化会使该次验收失败。

## 专项

| 范围 | 入口 |
| --- | --- |
| 声明说明符与模型 | `tests/c11_specifiers.py`、`tests/c11_declaration_model.py` |
| 作用域、标签与枚举 | `tests/c11_scopes.py`、`tests/c11_tags.py` |
| 初始化、泛型、静态字面量 | `tests/c11_initializers.py`、`tests/c11_generic.py`、`tests/c11_static_literals.py` |
| VLA、位域与成员布局 | `tests/c11_vm_layout.py` |
| 原子与地址对齐 | `tests/c11_atomics.py`、`tests/c11_atomic_alignment.py` |
| ABI 与无原型调用 | `tests/c11_abi.py`、`tests/c11_nonprototype_abi.py` |
| 复数与浮点环境 | `tests/c11_complex.py`、`tests/c11_fenv.py` |
| 线程与系统控制 | `tests/c11_threads.py`、`tests/c11_system_control.py` |
| 标准库与宽字符 | `tests/c11_library_contract.py`、`tests/c11_sdk_wide.py` |
| 预处理、packing、静态镜像 | `tests/c11_preprocessor.py`、`tests/c11_packing.py`、`tests/c11_static_images.py` |

全部队列的命令及报告复用见 [总验收](c11-full-support.md)。

## 重点检查

常量表达式区分整数常量表达式与静态算术初始化。`SourceConstant(value, isICE)` 保留来源属性到目标类型确定，避免将运行时的零误判为空指针常量。`sizeof` 保留未求值语义，`_Generic` 检查全部关联表达式，但只执行选中分支。

初始化测试覆盖 current-object 遍历、指定链、覆盖、数组推断及聚合表达式的一次求值。复合字面量检查同一块内的对象身份、递归帧隔离和重复初始化；分配规划器另由 `tests/allocation.py` 验证。

名字与类型测试检查声明点快照：后置原型、数组边界或标签定义不能修复此前的非法使用。旧式函数和无原型调用另以独立对象检查默认提升及 Windows x64 寄存器约定。

ABI 测试分别让 Naru 担任调用者和被调用者，对照对象由 Clang 或 MSVC 生成。系统头包含测试与库接口行为测试分开运行。

## 缺陷报告与目标选择

适用的解释参考 [WG14 C11/C17 issue log](https://open-std.org/JTC1/SC22/WG14/issues/c11c17/log.html)，记录原条款、处理状态及 Naru 的选择。当前重点包括 DR 423/481 的泛型控制表达式、DR 427 的参数/返回值及 DR 444/445 的对齐。

宿主扩展、实现定义行为和参考编译器差异分别登记。历史验证与工具链诊断见 [2026-10-23 记录](vyx-dist-20261023.md)。
